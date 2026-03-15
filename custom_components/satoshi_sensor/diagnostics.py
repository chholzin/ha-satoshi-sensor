"""Diagnostics support for Satoshi Sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, CONF_ENTRY_TYPE, CONF_XPUB, DOMAIN, ENTRY_TYPE_XPUB
from .coordinator import SatoshiSensorCoordinator, XpubCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    is_xpub = entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB

    # Redact sensitive identifiers (only show first/last 4 chars)
    if is_xpub:
        key = entry.data.get(CONF_XPUB, "")
        redacted_id = f"{key[:4]}…{key[-4:]}" if len(key) > 8 else "***"
    else:
        addr = entry.data.get(CONF_ADDRESS, "")
        redacted_id = f"{addr[:4]}…{addr[-4:]}" if len(addr) > 8 else "***"

    diag: dict[str, Any] = {
        "entry_type": entry.data.get(CONF_ENTRY_TYPE, "address"),
        "identifier": redacted_id,
        "update_interval_seconds": coordinator.update_interval.total_seconds(),
    }

    if coordinator.data:
        diag["last_update"] = {
            "balance_satoshi": coordinator.data.get("satoshi"),
            "balance_btc": coordinator.data.get("btc"),
            "fiat_value": coordinator.data.get("fiat"),
            "currency": coordinator.data.get("currency"),
            "btc_price": coordinator.data.get("price"),
            "price_change_24h": coordinator.data.get("price_change_24h"),
            "unconfirmed_satoshi": coordinator.data.get("unconfirmed_satoshi"),
            "tx_count": coordinator.data.get("tx_count"),
        }

        if is_xpub and isinstance(coordinator, XpubCoordinator):
            addresses = coordinator.data.get("addresses", {})
            diag["last_update"]["active_addresses"] = coordinator.data.get("address_count")
            diag["last_update"]["scanned_addresses"] = len(addresses)
            # Redact individual addresses
            diag["last_update"]["address_balances"] = {
                f"{addr[:4]}…{addr[-4:]}": bal
                for addr, bal in addresses.items()
            }
    else:
        diag["last_update"] = None

    if hasattr(coordinator, "_consecutive_errors"):
        diag["consecutive_errors"] = coordinator._consecutive_errors

    if hasattr(coordinator, "_mempool_url"):
        diag["mempool_url"] = coordinator._mempool_url

    return diag
