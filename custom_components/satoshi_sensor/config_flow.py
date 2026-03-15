"""Config flow for Satoshi Sensor."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ADDRESS,
    CONF_CURRENCY,
    CONF_LABEL,
    CONF_SCAN_INTERVAL,
    DEFAULT_CURRENCY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
    SUPPORTED_CURRENCIES,
)

BTC_ADDRESS_RE = re.compile(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,87}$")


def _address_schema(user_input: dict | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ADDRESS, default=(user_input or {}).get(CONF_ADDRESS, "")): str,
            vol.Optional(CONF_LABEL, default=(user_input or {}).get(CONF_LABEL, "")): str,
            vol.Optional(
                CONF_CURRENCY,
                default=(user_input or {}).get(CONF_CURRENCY, DEFAULT_CURRENCY),
            ): vol.In(SUPPORTED_CURRENCIES),
        }
    )


class SatoshiSensorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Satoshi Sensor."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            if not BTC_ADDRESS_RE.match(address):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                label = user_input.get(CONF_LABEL, "").strip() or address[:8] + "…"
                return self.async_create_entry(
                    title=label,
                    data={
                        CONF_ADDRESS: address,
                        CONF_LABEL: label,
                        CONF_CURRENCY: user_input.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_address_schema(user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SatoshiSensorOptionsFlow(config_entry)


class SatoshiSensorOptionsFlow(OptionsFlow):
    """Handle options (currency change)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_currency = self._entry.options.get(
            CONF_CURRENCY, self._entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        )
        current_interval = self._entry.options.get(
            CONF_SCAN_INTERVAL, self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CURRENCY, default=current_currency): vol.In(
                        SUPPORTED_CURRENCIES
                    ),
                    vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                        int, vol.Range(min=MIN_UPDATE_INTERVAL)
                    ),
                }
            ),
        )
