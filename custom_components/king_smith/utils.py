"""Utility classes and functions for the walkingpad integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

T = TypeVar("T")


def get_connectable_ble_device(
    hass: HomeAssistant, address: str, connectable: bool = True
) -> BLEDevice | None:
    """Resolve a BLEDevice for GATT connections.

    Prefer async_ble_device_from_address. If that is None (sparse advertisements or
    multiple scanners), fall back to async_scanner_devices_by_address and use the
    path with the strongest RSSI.
    """
    if device := bluetooth.async_ble_device_from_address(
        hass, address, connectable=connectable
    ):
        return device
    candidates = bluetooth.async_scanner_devices_by_address(
        hass, address, connectable=connectable
    )
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda c: (
            c.advertisement.rssi is not None,
            c.advertisement.rssi or -256,
        ),
    )
    return best.ble_device


class TemporaryValue(Generic[T]):
    """Generic temporary value with expiration."""

    def __init__(self) -> None:
        """Initialize temporary value."""
        self.has_value = False
        self.value: T | None = None
        self.expiration_timestamp = 0

    def set(self, value: T, expiration_timestamp: int) -> None:
        """Set a temporary value with expiration."""
        self.has_value = True
        self.value = value
        self.expiration_timestamp = expiration_timestamp

    def reset(self) -> None:
        """Reset the temporary value."""
        self.has_value = False

    def get(self, current_timestamp: int, default: T) -> T:
        """Get the temporary value or default, checking expiration."""
        if self.has_value and current_timestamp > self.expiration_timestamp:
            self.reset()
        if self.has_value and self.value is not None:
            return self.value
        return default

    def peek(self, default: T) -> T:
        """Get the temporary value or default without checking expiration."""
        if self.has_value and self.value is not None:
            return self.value
        return default
