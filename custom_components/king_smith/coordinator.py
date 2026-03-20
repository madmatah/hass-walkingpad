"""The Walking Pad Coordinator."""

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, BeltState, WalkingPadMode, WalkingPadStatus
from .walkingpad import WalkingPad

_LOGGER = logging.getLogger(__name__)

STATUS_UPDATE_INTERVAL = timedelta(seconds=5)

# The ph4_walkingpad has a 10s timeout in its connect method, you might have trouble if you set a smaller timeout here.
STATUS_UPDATE_TIMEOUT_SECONDS = 11

# How long to wait for the belt to fully stop before giving up and disconnecting.
DEFERRED_DISCONNECT_TIMEOUT_SECONDS = 30


class WalkingPadCoordinator(DataUpdateCoordinator[WalkingPadStatus]):
    """WalkingPad coordinator."""

    def __init__(self, hass: HomeAssistant, walkingpad_device: WalkingPad) -> None:
        """Initialise WalkingPad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            always_update=False,
            update_interval=STATUS_UPDATE_INTERVAL,
            update_method=None,
        )
        self.walkingpad_device = walkingpad_device
        self.walkingpad_device.register_status_callback(self._async_handle_update)
        self.data = {
            "belt_state": BeltState.STOPPED,
            "speed": 0.0,
            "mode": WalkingPadMode.MANUAL,
            "session_running_time": 0,
            "session_distance": 0,
            "session_steps": 0,
            "session_calories": 0,
            "status_timestamp": 0,
        }
        # Deferred disconnect: when set, the coordinator will call
        # async_set_stay_connected(False) once belt_state == STOPPED.
        self._deferred_disconnect_pending: bool = False
        self._deferred_disconnect_timeout_cancel: CALLBACK_TYPE | None = None

    async def _async_update_data(self) -> WalkingPadStatus:
        # When stay_connected is disabled, skip polling/auto-reconnect entirely.
        # Sensors will show stale data; commands handle their own connect/disconnect.
        if not self.walkingpad_device.stay_connected:
            return self.data

        async with asyncio.timeout(STATUS_UPDATE_TIMEOUT_SECONDS):
            await self.walkingpad_device.update_state()
            # We don't know the status yet, it will be transmitted to the _async_handle_update callback.
            # In the meantime, we return the current data to avoid any update (thanks to always_update=False).
            return self.data

    @property
    def connected(self) -> bool:
        """Get the device connection status."""
        return self.walkingpad_device.connected

    @callback
    def _async_handle_update(self, status: WalkingPadStatus) -> None:
        """Receive status updates from the WalkingPad controller."""
        if status.get("status_timestamp", 0) > self.data.get("status_timestamp", 0):
            _LOGGER.debug("WalkingPad status update : %s", status)
            self.async_set_updated_data(status)

            # Check deferred disconnect: once belt is fully stopped, disconnect.
            if (
                self._deferred_disconnect_pending
                and status.get("belt_state") == BeltState.STOPPED
            ):
                _LOGGER.info("Belt stopped, executing deferred disconnect")
                self._deferred_disconnect_pending = False
                self._cancel_deferred_disconnect_timeout()
                self.hass.async_create_task(
                    self.async_set_stay_connected(False),
                    "Deferred disconnect after belt stop",
                )

    @callback
    def _async_handle_disconnect(self) -> None:
        """Trigger the callbacks for disconnected."""
        self.async_update_listeners()

    async def _async_connect(self, *_) -> None:
        """Connect to the device."""
        await self.walkingpad_device.connect()

    async def _async_disconnect(self, *_) -> None:
        """Disconnect the device."""
        await self.walkingpad_device.disconnect()

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Connect the device and listen for data updates."""
        if not self._listeners and self.walkingpad_device.stay_connected:
            async_call_later(
                self.hass,
                0,
                HassJob(self._async_connect, "Connect to WalkingPad"),
            )
        return super().async_add_listener(update_callback, context)

    @callback
    def _unschedule_refresh(self) -> None:
        """Unschedule any pending refresh since there is no longer any listeners."""
        async_call_later(
            self.hass,
            0,
            HassJob(self._async_disconnect, "Disonnect the WalkingPad"),
        )
        return super()._unschedule_refresh()

    async def async_set_stay_connected(self, value: bool) -> None:
        """Handle the stay_connected toggle from the switch entity.

        When turned ON: set the property and trigger an immediate connect + poll.
        When turned OFF: set the property and disconnect immediately.
        """
        self.walkingpad_device.stay_connected = value
        if value:
            # User explicitly enabled stay_connected — cancel any pending
            # deferred disconnect so we don't disconnect out from under them.
            self._cancel_deferred_disconnect()
            # Reconnect and resume polling
            await self._async_connect()
        else:
            # Disconnect immediately to free BLE link for phone app
            await self._async_disconnect()

    def async_schedule_deferred_disconnect(self) -> None:
        """Schedule a disconnect that fires once the belt reaches STOPPED.

        Called by belt switch async_turn_off instead of an immediate
        async_set_stay_connected(False).  The coordinator keeps polling
        (stay_connected stays True) so the UI shows live deceleration data.
        Once _async_handle_update sees belt_state == STOPPED, it calls
        async_set_stay_connected(False).

        A timeout ensures we disconnect even if STOPPED is never observed
        (e.g. BLE drops during deceleration).
        """
        # If there's already a pending deferred disconnect, don't double-schedule.
        if self._deferred_disconnect_pending:
            _LOGGER.debug("Deferred disconnect already pending, ignoring")
            return

        _LOGGER.info(
            "Scheduling deferred disconnect (timeout=%ss)",
            DEFERRED_DISCONNECT_TIMEOUT_SECONDS,
        )
        self._deferred_disconnect_pending = True

        # Safety timeout — disconnect anyway if we never see STOPPED.
        self._deferred_disconnect_timeout_cancel = async_call_later(
            self.hass,
            DEFERRED_DISCONNECT_TIMEOUT_SECONDS,
            HassJob(
                self._async_deferred_disconnect_timeout,
                "Deferred disconnect timeout",
            ),
        )

    async def _async_deferred_disconnect_timeout(self, *_) -> None:
        """Handle timeout when belt never reached STOPPED state."""
        if not self._deferred_disconnect_pending:
            return
        _LOGGER.warning(
            "Deferred disconnect timed out after %ss — disconnecting anyway",
            DEFERRED_DISCONNECT_TIMEOUT_SECONDS,
        )
        self._deferred_disconnect_pending = False
        self._deferred_disconnect_timeout_cancel = None
        await self.async_set_stay_connected(False)

    def _cancel_deferred_disconnect(self) -> None:
        """Cancel any pending deferred disconnect (flag + timeout)."""
        if self._deferred_disconnect_pending:
            _LOGGER.debug("Cancelling pending deferred disconnect")
        self._deferred_disconnect_pending = False
        self._cancel_deferred_disconnect_timeout()

    def _cancel_deferred_disconnect_timeout(self) -> None:
        """Cancel the deferred disconnect timeout timer if running."""
        if self._deferred_disconnect_timeout_cancel is not None:
            self._deferred_disconnect_timeout_cancel()
            self._deferred_disconnect_timeout_cancel = None
