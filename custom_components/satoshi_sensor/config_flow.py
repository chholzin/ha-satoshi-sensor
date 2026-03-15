"""Config flow for Satoshi Sensor."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow

from .const import (
    CONF_ADDRESS,
    CONF_CURRENCY,
    CONF_ENTRY_TYPE,
    CONF_LABEL,
    CONF_SCAN_INTERVAL,
    CONF_XPUB,
    DEFAULT_CURRENCY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_ADDRESS,
    ENTRY_TYPE_XPUB,
    MIN_UPDATE_INTERVAL,
    SUPPORTED_CURRENCIES,
    XPUB_PREFIXES,
)

_LOGGER = logging.getLogger(__name__)

BTC_ADDRESS_RE = re.compile(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,87}$")


def _validate_xpub(xpub: str) -> bool:
    return xpub[:4].lower() in XPUB_PREFIXES and len(xpub) >= 100


def _test_derive(xpub: str) -> None:
    from .xpub import derive_addresses
    derive_addresses(xpub, 0, 1)


class SatoshiSensorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Satoshi Sensor."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_ENTRY_TYPE] == ENTRY_TYPE_XPUB:
                return await self.async_step_xpub()
            return await self.async_step_address()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTRY_TYPE, default=ENTRY_TYPE_ADDRESS): vol.In(
                        [ENTRY_TYPE_ADDRESS, ENTRY_TYPE_XPUB]
                    )
                }
            ),
        )

    async def async_step_address(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
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
                        CONF_ENTRY_TYPE: ENTRY_TYPE_ADDRESS,
                        CONF_ADDRESS: address,
                        CONF_LABEL: label,
                        CONF_CURRENCY: user_input.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                    },
                )

        return self.async_show_form(
            step_id="address",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default=""): str,
                    vol.Optional(CONF_LABEL, default=""): str,
                    vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): vol.In(
                        SUPPORTED_CURRENCIES
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_xpub(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            xpub = user_input[CONF_XPUB].strip()
            if not _validate_xpub(xpub):
                errors[CONF_XPUB] = "invalid_xpub"
            else:
                try:
                    await self.hass.async_add_executor_job(_test_derive, xpub)
                except Exception as exc:
                    _LOGGER.exception("xpub derivation failed: %s", exc)
                    errors[CONF_XPUB] = "invalid_xpub"

            if not errors:
                await self.async_set_unique_id(f"xpub_{xpub}")
                self._abort_if_unique_id_configured()
                label = user_input.get(CONF_LABEL, "").strip() or xpub[:8] + "…"
                return self.async_create_entry(
                    title=label,
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_XPUB,
                        CONF_XPUB: xpub,
                        CONF_LABEL: label,
                        CONF_CURRENCY: user_input.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                    },
                )

        return self.async_show_form(
            step_id="xpub",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_XPUB, default=""): str,
                    vol.Optional(CONF_LABEL, default=""): str,
                    vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): vol.In(
                        SUPPORTED_CURRENCIES
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SatoshiSensorOptionsFlow()


class SatoshiSensorOptionsFlow(OptionsFlow):
    """Handle options (currency and interval)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_currency = self.config_entry.options.get(
            CONF_CURRENCY, self.config_entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        )
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
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
