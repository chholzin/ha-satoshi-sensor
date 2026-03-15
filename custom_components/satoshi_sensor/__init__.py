"""Satoshi Sensor — Bitcoin wallet balance integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_ADDRESS,
    CONF_CURRENCY,
    CONF_ENTRY_TYPE,
    CONF_SCAN_INTERVAL,
    CONF_XPUB,
    DEFAULT_CURRENCY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_XPUB,
)
from .coordinator import SatoshiSensorCoordinator, XpubCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    currency = entry.options.get(CONF_CURRENCY, entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY))
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )

    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB:
        coordinator = XpubCoordinator(hass, entry.data[CONF_XPUB], currency, scan_interval)
    else:
        coordinator = SatoshiSensorCoordinator(
            hass, entry.data[CONF_ADDRESS], currency, scan_interval
        )

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady(f"Could not fetch initial data: {err}") from err
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _LOGGER.info("Set up entry %s (%s)", entry.title, entry.data.get(CONF_ENTRY_TYPE, "address"))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change (e.g. currency or interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
