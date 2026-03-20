"""Walkingpad number support."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
from .coordinator import WalkingPadCoordinator

NUMBER_KEY = "walkingpad_speed"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WalkingPad number."""

    remote_control_enabled = entry.options.get(CONF_REMOTE_CONTROL_ENABLED, False)
    preferred_mode = entry.options.get(CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE)
    manual_mode = WalkingPadMode.MANUAL.name.lower()

    if not (remote_control_enabled and preferred_mode == manual_mode):
        entity_registry = er.async_get(hass)
        mac_address = entry.data.get(CONF_MAC)
        unique_id = f"{mac_address}-{NUMBER_KEY}"

        entity_id = entity_registry.async_get_entity_id("number", DOMAIN, unique_id)
        if entity_id:
            entity_registry.async_remove(entity_id)
        return

    entry_data: WalkingPadIntegrationData = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    async_add_entities([WalkingPadSpeedNumberEntity(coordinator)])


class WalkingPadSpeedNumberEntity(
    CoordinatorEntity[WalkingPadCoordinator], NumberEntity
):
    """Represent the WalkingPad speed number."""

    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_has_entity_name = True
    _attr_translation_key = "walkingpad_speed"

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the speed number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.walkingpad_device.mac}-{NUMBER_KEY}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.walkingpad_device.mac)},
            name=coordinator.walkingpad_device.name,
            manufacturer="KingSmith",
        )

    @property
    def native_min_value(self) -> float:
        """Return min speed from device capabilities (updates after connection)."""
        return self.coordinator.walkingpad_device.min_speed

    @property
    def native_max_value(self) -> float:
        """Return max speed from device capabilities (updates after connection)."""
        return self.coordinator.walkingpad_device.max_speed

    @property
    def native_step(self) -> float:
        """Return speed increment from device capabilities (updates after connection)."""
        return self.coordinator.walkingpad_device.speed_increment

    @property
    def native_value(self) -> float:
        """Return the current speed."""
        return self.coordinator.data.get("speed", 0.0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the speed.

        For FTMS devices, setting a target speed also starts the belt,
        so we allow speed changes even when the belt is stopped.
        For legacy devices, speed can only be changed when the belt is active.
        """
        from .const import ProtocolType

        device = self.coordinator.walkingpad_device
        belt_state = self.coordinator.data.get("belt_state")

        # Legacy devices require the belt to be running before changing speed
        if device.protocol == ProtocolType.WILINK and belt_state not in [
            BeltState.ACTIVE,
            BeltState.STARTING,
        ]:
            return

        await device.set_speed(value)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected
