"""Walkingpad switch support."""

import logging
from abc import ABC
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import WalkingPadIntegrationData
from .const import (
    CONF_MAC,
    CONF_PREFERRED_MODE,
    CONF_REMOTE_CONTROL_ENABLED,
    DEFAULT_PREFERRED_MODE,
    DOMAIN,
    BeltState,
    WalkingPadMode,
)
from .coordinator import STATUS_UPDATE_INTERVAL, WalkingPadCoordinator
from .utils import TemporaryValue

_LOGGER = logging.getLogger(__name__)

SWITCH_KEY = "walkingpad_belt_switch"
STAY_CONNECTED_KEY = "walkingpad_stay_connected"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WalkingPad switch."""
    entry_data: WalkingPadIntegrationData = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    entities: list[SwitchEntity] = []

    # Stay Connected switch is always created (not gated by remote_control)
    entities.append(WalkingPadStayConnectedSwitch(coordinator))

    # Belt control switches are gated by remote_control_enabled
    if entry.options.get(CONF_REMOTE_CONTROL_ENABLED, False):
        preferred_mode = entry.options.get(CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE)
        manual_mode = WalkingPadMode.MANUAL.name.lower()

        if preferred_mode == manual_mode:
            entities.append(WalkingPadBeltSwitchManual(coordinator))
        else:
            entities.append(WalkingPadBeltSwitchAuto(coordinator))
    else:
        # Clean up belt switch entity if remote_control was disabled
        entity_registry = er.async_get(hass)
        mac_address = entry.data.get(CONF_MAC)
        unique_id = f"{mac_address}-{SWITCH_KEY}"

        entity_id = entity_registry.async_get_entity_id("switch", DOMAIN, unique_id)
        if entity_id:
            entity_registry.async_remove(entity_id)

    async_add_entities(entities)


class WalkingPadBeltSwitchBase(SwitchEntity, ABC):
    """Base class for WalkingPad belt switch entities."""

    entity_description: SwitchEntityDescription
    coordinator: WalkingPadCoordinator
    _temporary_belt_state: TemporaryValue[BeltState]
    _temporary_mode: TemporaryValue[WalkingPadMode]

    @staticmethod
    def _create_entity_description(translation_key: str) -> SwitchEntityDescription:
        """Create an entity description with the given translation key."""
        return SwitchEntityDescription(
            device_class=SwitchDeviceClass.SWITCH,
            icon="mdi:cog-play",
            key=SWITCH_KEY,
            translation_key=translation_key,
            has_entity_name=True,
        )

    def __init__(self, coordinator: WalkingPadCoordinator):
        """Initialize the belt switch."""
        self._temporary_belt_state = TemporaryValue[BeltState]()
        self._temporary_mode = TemporaryValue[WalkingPadMode]()
        self.coordinator = coordinator
        self.entity_description = self._create_entity_description(
            "walkingpad_belt_switch"
        )
        self._attr_unique_id = (
            f"{coordinator.walkingpad_device.mac}-{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.walkingpad_device.mac)},
            name=coordinator.walkingpad_device.name,
            manufacturer="KingSmith",
        )
        super().__init__()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        current_timestamp = self.coordinator.data.get("status_timestamp", 0)
        current_belt_state = self.coordinator.data.get("belt_state")

        # Check expiration for temporary belt state with special condition
        # Don't reset if belt is starting (to keep temporary state during startup)
        if (
            self._temporary_belt_state.has_value
            and current_belt_state != BeltState.STARTING
            and current_timestamp > self._temporary_belt_state.expiration_timestamp
        ):
            self._temporary_belt_state.reset()

        # Use temporary value if available (without auto-expiration check),
        # otherwise use current state
        belt_state = self._temporary_belt_state.peek(
            current_belt_state or BeltState.STOPPED
        )

        return belt_state in [BeltState.ACTIVE, BeltState.STARTING]

    def set_temporary_belt_state(self, belt_state: BeltState) -> None:
        """Set a temporary belt state."""
        expiration_timestamp = (
            self.coordinator.data.get("status_timestamp", 0)
            + STATUS_UPDATE_INTERVAL.total_seconds()
        )
        self._temporary_belt_state.set(belt_state, expiration_timestamp)

    def set_temporary_mode(self, mode: WalkingPadMode) -> None:
        """Set a temporary mode."""
        expiration_timestamp = (
            self.coordinator.data.get("status_timestamp", 0)
            + STATUS_UPDATE_INTERVAL.total_seconds()
        )
        self._temporary_mode.set(mode, expiration_timestamp)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        raise NotImplementedError

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        raise NotImplementedError


class WalkingPadBeltSwitchManual(WalkingPadBeltSwitchBase):
    """Represent the WalkingPad belt switch in manual mode."""

    def __init__(self, coordinator: WalkingPadCoordinator):
        """Initialize the belt switch."""
        super().__init__(coordinator)
        self.entity_description = self._create_entity_description(
            "walkingpad_belt_switch_manual"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.set_temporary_mode(WalkingPadMode.MANUAL)
        self.set_temporary_belt_state(BeltState.STARTING)
        await self.coordinator.async_set_stay_connected(True)
        current_mode = self.coordinator.data.get("mode")
        if current_mode != WalkingPadMode.MANUAL:
            await self.coordinator.walkingpad_device.start_belt_in_mode(
                WalkingPadMode.MANUAL
            )
        else:
            await self.coordinator.walkingpad_device.start_belt()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.set_temporary_belt_state(BeltState.STOPPED)
        await self.coordinator.walkingpad_device.stop_belt()
        self.coordinator.async_schedule_deferred_disconnect()


class WalkingPadBeltSwitchAuto(WalkingPadBeltSwitchBase):
    """Represent the WalkingPad belt switch in auto mode."""

    def __init__(self, coordinator: WalkingPadCoordinator):
        """Initialize the belt switch."""
        super().__init__(coordinator)
        self.entity_description = self._create_entity_description(
            "walkingpad_belt_switch_auto"
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        current_timestamp = self.coordinator.data.get("status_timestamp", 0)
        current_mode = self.coordinator.data.get("mode")
        current_belt_state = self.coordinator.data.get("belt_state")

        mode = self._temporary_mode.get(
            current_timestamp, current_mode or WalkingPadMode.MANUAL
        )
        belt_state = self._temporary_belt_state.get(
            current_timestamp, current_belt_state or BeltState.STOPPED
        )

        if mode == WalkingPadMode.AUTO:
            return True
        if mode == WalkingPadMode.STANDBY:
            return False
        return belt_state in [BeltState.ACTIVE, BeltState.STARTING]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.set_temporary_mode(WalkingPadMode.AUTO)
        await self.coordinator.async_set_stay_connected(True)
        await self.coordinator.walkingpad_device.switch_mode(WalkingPadMode.AUTO)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.set_temporary_mode(WalkingPadMode.STANDBY)
        self.set_temporary_belt_state(BeltState.STOPPED)
        await self.coordinator.walkingpad_device.switch_mode(WalkingPadMode.STANDBY)
        self.coordinator.async_schedule_deferred_disconnect()


class WalkingPadStayConnectedSwitch(SwitchEntity, RestoreEntity):
    """Switch to control whether HA maintains a persistent BLE connection.

    When ON (default): HA stays connected, coordinator polls every 5s, sensors
    update live.  This is the normal behavior.

    When OFF: HA disconnects immediately, freeing the BLE link so the user's
    smartphone app (e.g. KS Fit) can connect for tracking.  Commands (belt
    on/off, speed) will still work — they connect, send the command, then
    disconnect right away.  Sensors go stale until stay_connected is re-enabled.

    State is persisted across HA restarts via RestoreEntity.
    """

    entity_description: SwitchEntityDescription

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the stay connected switch."""
        self.coordinator = coordinator
        self.entity_description = SwitchEntityDescription(
            device_class=SwitchDeviceClass.SWITCH,
            icon="mdi:bluetooth-connect",
            key=STAY_CONNECTED_KEY,
            translation_key=STAY_CONNECTED_KEY,
            has_entity_name=True,
        )
        self._attr_unique_id = (
            f"{coordinator.walkingpad_device.mac}-{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.walkingpad_device.mac)},
            name=coordinator.walkingpad_device.name,
            manufacturer="KingSmith",
        )
        super().__init__()

    @property
    def is_on(self) -> bool:
        """Return the live stay_connected state from the device."""
        return self.coordinator.walkingpad_device.stay_connected

    async def async_added_to_hass(self) -> None:
        """Restore state after HA restart and subscribe to coordinator updates."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            restored = last_state.state == "on"
            _LOGGER.info(
                "Restoring stay_connected state: %s (was %s)",
                restored,
                last_state.state,
            )
            self.coordinator.walkingpad_device.stay_connected = restored
        else:
            _LOGGER.info("No previous stay_connected state, defaulting to ON")
            self.coordinator.walkingpad_device.stay_connected = True

        # Subscribe to coordinator updates so our UI state refreshes when
        # belt switches toggle stay_connected via the coordinator.
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """React to coordinator data updates by refreshing our HA state."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on — re-enable persistent BLE connection."""
        await self.coordinator.async_set_stay_connected(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off — disconnect BLE to free link for phone app."""
        await self.coordinator.async_set_stay_connected(False)
        self.async_write_ha_state()
