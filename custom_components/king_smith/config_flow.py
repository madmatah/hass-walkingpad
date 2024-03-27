"""Config flow for walkingpad integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC, "MAC Address"): str,
        vol.Required(CONF_NAME, "Device name"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    ble_device = bluetooth.async_ble_device_from_address(
        hass, data[CONF_MAC], connectable=True
    )
    if ble_device is None:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {CONF_MAC: ble_device.address, CONF_NAME: data[CONF_NAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for walkingpad."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception %s", e)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(dr.format_mac(info[CONF_MAC]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info[CONF_NAME], data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(dr.format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        # pylint: disable=attribute-defined-outside-init
        self.discovered_device = {
            "local_name": discovery_info.name,
            "address": discovery_info.address,
        }
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setting up a device."""
        if not user_input:
            dev_name = self.discovered_device["local_name"]
            dev_address = self.discovered_device["address"]

            schema_mac = vol.In([f"{dev_name} ({dev_address})"])
            schema = vol.Schema(
                {
                    vol.Required(CONF_MAC): schema_mac,
                    vol.Required(
                        CONF_NAME,
                        default=dev_name,
                        msg="Name",
                        description="Device name",
                    ): str,
                }
            )
            return self.async_show_form(step_id="device", data_schema=schema)

        user_input[CONF_MAC] = self.discovered_device["address"]
        await self.async_set_unique_id(self.discovered_device["address"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
