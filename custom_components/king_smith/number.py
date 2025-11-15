"""Walkingpad number support."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WalkingPadIntegrationData
from .const import CONF_MAC, CONF_REMOTE_CONTROL_ENABLED, DOMAIN, BeltState
from .coordinator import WalkingPadCoordinator

NUMBER_KEY = "walkingpad_speed"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WalkingPad number."""

    if not entry.options.get(CONF_REMOTE_CONTROL_ENABLED, False):
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

    _attr_native_min_value = 0.5
    _attr_native_max_value = 6.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_has_entity_name = True
    _attr_translation_key = "walkingpad_speed"

    def __init__(self, coordinator: WalkingPadCoordinator) -> None:
        """Initialize the speed number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.walkingpad_device.mac}-{NUMBER_KEY}"

    @property
    def native_value(self) -> float:
        """Return the current speed."""
        return self.coordinator.data.get("speed", 0.0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the speed."""
        belt_state = self.coordinator.data.get("belt_state")
        if belt_state not in [BeltState.ACTIVE, BeltState.STARTING]:
            return
        await self.coordinator.walkingpad_device.set_speed(value)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected
