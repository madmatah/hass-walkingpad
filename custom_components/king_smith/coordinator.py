"""The Walking Pad Coordinator."""
import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
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
            "status_timestamp": 0,
        }

    async def _async_update_data(self) -> WalkingPadStatus:
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
        if not self._listeners:
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
