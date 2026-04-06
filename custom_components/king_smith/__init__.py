"""The walkingpad integration."""

from __future__ import annotations

import logging
from typing import TypedDict

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers import device_registry as dr

from .const import CONF_MAC, CONF_NAME, DOMAIN
from .coordinator import WalkingPadCoordinator
from .walkingpad import WalkingPad

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]


class WalkingPadIntegrationData(TypedDict):
    """A type to represent the data stored by the integration for each entity."""

    device: WalkingPad
    coordinator: WalkingPadCoordinator
    device_entry: DeviceEntry


_LOGGER = logging.getLogger(__name__)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options and reload platforms."""
    await hass.config_entries.async_unload_platforms(
        entry, [Platform.SWITCH, Platform.NUMBER]
    )
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SWITCH, Platform.NUMBER]
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up walkingpad from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    address = entry.data.get(CONF_MAC)

    ble_device = bluetooth.async_ble_device_from_address(
        hass, entry.data.get(CONF_MAC), connectable=True
    )
    if ble_device is None:
        # Check if any HA scanner on:
        count_scanners = bluetooth.async_scanner_count(hass, connectable=True)
        if count_scanners < 1:
            raise ConfigEntryNotReady(
                "No bluetooth scanner detected. \
                Enable the bluetooth integration or ensure an esphome device \
                is running as a bluetooth proxy"
            )
        raise ConfigEntryNotReady(f"Could not find Walkingpad with address {address}")

    name = entry.data.get(CONF_NAME) or DOMAIN
    walkingpad_device = WalkingPad(name, ble_device)
    coordinator = WalkingPadCoordinator(hass, walkingpad_device)

    # Obtener nombre del dispositivo BLE
    ble_name = ble_device.name or "WalkingPad"
    
    # Crear el dispositivo en el registro de dispositivos
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        identifiers={(DOMAIN, address)},
        name=name or ble_name,
        manufacturer="King Smith",
        model=ble_name or "WalkingPad A1 Pro",
        hw_version=None,
        sw_version=None,
    )

    integration_data: WalkingPadIntegrationData = {
        "device": walkingpad_device,
        "coordinator": coordinator,
        "device_entry": device_entry,
    }
    hass.data[DOMAIN][entry.entry_id] = integration_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
