"""Walkingpad switch support."""

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
from .const import CONF_MAC, CONF_REMOTE_CONTROL_ENABLED, DOMAIN, BeltState
from .coordinator import STATUS_UPDATE_INTERVAL, WalkingPadCoordinator

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

    async_add_entities([WalkingPadBeltSwitchEntity(coordinator)])


class WalkingPadBeltSwitchEntity(SwitchEntity):
    """Represent the WalkingPad belt switch."""

    entity_description: SwitchEntityDescription
    coordinator: WalkingPadCoordinator
    has_temporary_state: bool
    temporary_state: BeltState
    temporary_state_expiration_timestamp: int

    def __init__(self, coordinator: WalkingPadCoordinator):
        """Initialize the belt switch."""
        self.has_temporary_state = False
        self.temporary_state = BeltState.STOPPED
        self.temporary_state_expiration_timestamp = 0
        self.coordinator = coordinator
        self.entity_description = SwitchEntityDescription(
            device_class=SwitchDeviceClass.SWITCH,
            icon="mdi:cog-play",
            key=SWITCH_KEY,
            translation_key="walkingpad_belt_switch",
            has_entity_name=True,
        )
        self._attr_unique_id = (
            f"{coordinator.walkingpad_device.mac}-{self.entity_description.key}"
        )
        super().__init__()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if (
            self.has_temporary_state
            and self.coordinator.data.get("belt_state") != BeltState.STARTING
            and self.coordinator.data.get("status_timestamp")
            > self.temporary_state_expiration_timestamp
        ):
            self.reset_temporary_state()

        current_state = (
            self.temporary_state
            if self.has_temporary_state
            else self.coordinator.data.get("belt_state")
        )
        return current_state in [BeltState.ACTIVE, BeltState.STARTING]

    def set_temporary_state(self, belt_state: BeltState) -> None:
        """Set a temporary belt state."""
        self.has_temporary_state = True
        self.temporary_state = belt_state
        self.temporary_state_expiration_timestamp = (
            self.coordinator.data.get("status_timestamp")
            + STATUS_UPDATE_INTERVAL.total_seconds()
        )

    def reset_temporary_state(self) -> None:
        """Reset the temporary belt state."""
        self.has_temporary_state = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.set_temporary_state(BeltState.STARTING)
        await self.coordinator.walkingpad_device.start_belt()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.set_temporary_state(BeltState.STOPPED)
        await self.coordinator.walkingpad_device.stop_belt()
