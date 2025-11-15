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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WalkingPadIntegrationData
from .const import DOMAIN, BeltState, WalkingPadMode, WalkingPadStatus
from .coordinator import WalkingPadCoordinator


@dataclass(kw_only=True)
class WalkingPadSensorEntityDescription(SensorEntityDescription):
    """Describes Example sensor entity."""

    value_fn: Callable[[WalkingPadStatus], StateType]


SENSORS: tuple[WalkingPadSensorEntityDescription, ...] = (
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
        icon="mdi:shoe-print",
        key="walkingpad_steps",
        name=None,
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        translation_key="walkingpad_steps",
        value_fn=lambda status: status.get("session_steps", 0),
    ),
    WalkingPadSensorEntityDescription(
        icon="mdi:timer",
        key="walkingpad_duration_minutes",
        name=None,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        translation_key="walkingpad_duration_minutes",
        value_fn=lambda status: round(status.get("session_running_time", 0) / 60, 1),
    ),
    WalkingPadSensorEntityDescription(
        icon="mdi:timer",
        key="walkingpad_duration_hours",
        name=None,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        translation_key="walkingpad_duration_hours",
        value_fn=lambda status: round(status.get("session_running_time", 0) / 3600, 4),
    ),
    WalkingPadSensorEntityDescription(
        icon="mdi:timer",
        key="walkingpad_duration_days",
        name=None,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        translation_key="walkingpad_duration_days",
        value_fn=lambda status: round(status.get("session_running_time", 0) / 86400, 6),
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
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WalkingPad sensors."""

    entry_data: WalkingPadIntegrationData = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    async_add_entities(
        WalkingPadSensor(coordinator, description) for description in SENSORS
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

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.connected
