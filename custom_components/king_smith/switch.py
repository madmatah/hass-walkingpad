"""Walkingpad switch support."""

import asyncio
from abc import ABC
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

SWITCH_KEY = "walkingpad_belt_switch"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WalkingPad switch."""

    if not entry.options.get(CONF_REMOTE_CONTROL_ENABLED, False):
        entity_registry = er.async_get(hass)
        mac_address = entry.data.get(CONF_MAC)
        unique_id = f"{mac_address}-{SWITCH_KEY}"

        entity_id = entity_registry.async_get_entity_id("switch", DOMAIN, unique_id)
        if entity_id:
            entity_registry.async_remove(entity_id)
        return

    entry_data: WalkingPadIntegrationData = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    preferred_mode = entry.options.get(CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE)
    manual_mode = WalkingPadMode.MANUAL.name.lower()

    if preferred_mode == manual_mode:
        async_add_entities([WalkingPadBeltSwitchManual(coordinator)])
    else:
        async_add_entities([WalkingPadBeltSwitchAuto(coordinator)])


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
        current_mode = self.coordinator.data.get("mode")
        if current_mode != WalkingPadMode.MANUAL:
            await self.coordinator.walkingpad_device.switch_mode(WalkingPadMode.MANUAL)
            await asyncio.sleep(1.5)
        self.set_temporary_mode(WalkingPadMode.MANUAL)
        self.set_temporary_belt_state(BeltState.STARTING)
        await self.coordinator.walkingpad_device.start_belt()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.set_temporary_belt_state(BeltState.STOPPED)
        await self.coordinator.walkingpad_device.stop_belt()


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
        await self.coordinator.walkingpad_device.switch_mode(WalkingPadMode.AUTO)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.set_temporary_mode(WalkingPadMode.STANDBY)
        self.set_temporary_belt_state(BeltState.STOPPED)
        await self.coordinator.walkingpad_device.switch_mode(WalkingPadMode.STANDBY)
