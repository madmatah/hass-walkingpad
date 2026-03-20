"""WalkingPad sensor support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WalkingPadIntegrationData
from .const import DOMAIN, BeltState, ProtocolType, WalkingPadMode, WalkingPadStatus
from .coordinator import WalkingPadCoordinator


@dataclass(kw_only=True)
class WalkingPadSensorEntityDescription(SensorEntityDescription):
    """Describes Example sensor entity."""

    value_fn: Callable[[WalkingPadStatus], StateType]


# Sensors available for all protocol types.
COMMON_SENSORS: tuple[WalkingPadSensorEntityDescription, ...] = (
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:walk",
        key="walkingpad_distance",
        name=None,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        translation_key="walkingpad_distance",
        value_fn=lambda status: status.get("session_distance", 0.0) / 1000,
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer",
        key="walkingpad_duration",
        name=None,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        translation_key="walkingpad_duration",
        value_fn=lambda status: status.get("session_running_time", 0),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:speedometer",
        key="walkingpad_current_speed",
        name=None,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="walkingpad_current_speed",
        value_fn=lambda status: status.get("speed", 0.0),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:state-machine",
        key="walkingpad_state",
        name=None,
        options=[e.name.lower() for e in BeltState],
        translation_key="walkingpad_state",
        value_fn=lambda status: status.get(
            "belt_state", BeltState.UNKNOWN
        ).name.lower(),
    ),
    WalkingPadSensorEntityDescription(
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:cog",
        key="walkingpad_mode",
        name=None,
        options=[e.name.lower() for e in WalkingPadMode],
        translation_key="walkingpad_mode",
        value_fn=lambda status: status.get("mode", WalkingPadMode.MANUAL).name.lower(),
    ),
    WalkingPadSensorEntityDescription(
        icon="mdi:shoe-print",
        key="walkingpad_steps",
        name=None,
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        translation_key="walkingpad_steps",
        value_fn=lambda status: status.get("session_steps", 0),
    ),
)

# Sensors only available for FTMS devices (calories reported via FTMS Expended Energy).
FTMS_SENSORS: tuple[WalkingPadSensorEntityDescription, ...] = (
    WalkingPadSensorEntityDescription(
        icon="mdi:fire",
        key="walkingpad_calories",
        name=None,
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        translation_key="walkingpad_calories",
        value_fn=lambda status: status.get("session_calories", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WalkingPad sensors."""

    entry_data: WalkingPadIntegrationData = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    device = entry_data["device"]

    # Build sensor list based on protocol type.
    # Steps are in COMMON_SENSORS (available for both WiLink and FTMS).
    sensors: list[WalkingPadSensorEntityDescription] = list(COMMON_SENSORS)

    if device.protocol == ProtocolType.FTMS:
        sensors.extend(FTMS_SENSORS)

    async_add_entities(
        WalkingPadSensor(coordinator, description) for description in sensors
    )


class WalkingPadSensor(
    CoordinatorEntity[WalkingPadCoordinator],
    SensorEntity,
):
    """Represent a WalkingPad sensor."""

    entity_description: WalkingPadSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WalkingPadCoordinator,
        entity_description: WalkingPadSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.walkingpad_device.mac}-{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.walkingpad_device.mac)},
            name=coordinator.walkingpad_device.name,
            manufacturer="KingSmith",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected
