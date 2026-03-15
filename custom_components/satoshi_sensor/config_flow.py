"""Config flow for Satoshi Sensor."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult  # type: ignore[assignment]

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

_CONF_WALLET = "wallet"

BTC_ADDRESS_RE = re.compile(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,87}$")


def _validate_xpub(xpub: str) -> bool:
    return xpub[:4].lower() in XPUB_PREFIXES and len(xpub) >= 100


def _test_derive(xpub: str) -> str:
    """Try to derive one address; return a specific error key on failure."""
    from .xpub import derive_addresses
    try:
        derive_addresses(xpub, 0, 1)
    except ValueError as exc:
        msg = str(exc).lower()
        if "checksum" in msg:
            return "xpub_bad_checksum"
        if "78 bytes" in msg or "length" in msg:
            return "xpub_bad_length"
        return "xpub_derivation_failed"
    except Exception:
        return "xpub_derivation_failed"
    return ""


class SatoshiSensorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Satoshi Sensor."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            wallet = user_input[_CONF_WALLET].strip()
            label = user_input.get(CONF_LABEL, "").strip()
            currency = user_input.get(CONF_CURRENCY, DEFAULT_CURRENCY)

            if _validate_xpub(wallet):
                error_key = await self.hass.async_add_executor_job(_test_derive, wallet)
                if error_key:
                    _LOGGER.warning("xpub validation failed (%s): %s", error_key, wallet[:12])
                    errors[_CONF_WALLET] = error_key

                if not errors:
                    await self.async_set_unique_id(f"xpub_{wallet}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=label or wallet[:8] + "…",
                        data={
                            CONF_ENTRY_TYPE: ENTRY_TYPE_XPUB,
                            CONF_XPUB: wallet,
                            CONF_LABEL: label or wallet[:8] + "…",
                            CONF_CURRENCY: currency,
                        },
                    )
            elif BTC_ADDRESS_RE.match(wallet):
                await self.async_set_unique_id(wallet)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=label or wallet[:8] + "…",
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_ADDRESS,
                        CONF_ADDRESS: wallet,
                        CONF_LABEL: label or wallet[:8] + "…",
                        CONF_CURRENCY: currency,
                    },
                )
            else:
                errors[_CONF_WALLET] = "invalid_wallet"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(_CONF_WALLET, default=""): str,
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
