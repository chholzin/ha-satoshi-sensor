"""Satoshi Sensor — Bitcoin wallet balance integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import UpdateFailed

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_ADDRESS,
    CONF_CURRENCY,
    CONF_ENTRY_TYPE,
    CONF_MEMPOOL_URL,
    CONF_SCAN_INTERVAL,
    CONF_XPUB,
    CONF_XPUB_CONCURRENCY,
    DEFAULT_CURRENCY,
    DEFAULT_MEMPOOL_URL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_STATS,
    ENTRY_TYPE_TOTALS,
    ENTRY_TYPE_XPUB,
    SIGNAL_TOTALS_UPDATE,
    STATS_UNIQUE_ID,
    TOTALS_UNIQUE_ID,
)
from .coordinator import SatoshiSensorCoordinator, StatsCoordinator, XpubCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Portfolio Total — no coordinator, just forward to sensor platform
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TOTALS:
        hass.data.setdefault(DOMAIN, {})
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True

    currency = entry.options.get(CONF_CURRENCY, entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY))
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )
    mempool_url = entry.options.get(
        CONF_MEMPOOL_URL, entry.data.get(CONF_MEMPOOL_URL, DEFAULT_MEMPOOL_URL)
    )

    # Satoshi Stats — network statistics coordinator
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATS:
        coordinator = StatsCoordinator(hass, currency, scan_interval, mempool_url)
        restored = await coordinator.async_restore_last_data()
        if not restored:
            try:
                await coordinator.async_config_entry_first_refresh()
            except UpdateFailed as err:
                raise ConfigEntryNotReady(f"Could not fetch stats: {err}") from err
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        if restored:
            hass.async_create_task(coordinator.async_refresh())
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        return True

    # Wallet entry (address or xpub)
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB:
        concurrency = entry.options.get(CONF_XPUB_CONCURRENCY)
        coordinator = XpubCoordinator(
            hass, entry.data[CONF_XPUB], currency, scan_interval, mempool_url, concurrency
        )
    else:
        coordinator = SatoshiSensorCoordinator(
            hass, entry.data[CONF_ADDRESS], currency, scan_interval, mempool_url
        )

    restored = await coordinator.async_restore_last_data()
    if not restored:
        try:
            await coordinator.async_config_entry_first_refresh()
        except UpdateFailed as err:
            raise ConfigEntryNotReady(f"Could not fetch initial data: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _LOGGER.info(
        "Set up entry %s (%s)%s",
        entry.title,
        entry.data.get(CONF_ENTRY_TYPE, "address"),
        " (restored from cache)" if restored else "",
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if restored:
        hass.async_create_task(coordinator.async_refresh())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Auto-create Portfolio Total and Satoshi Stats if not yet present
    existing = hass.config_entries.async_entries(DOMAIN)
    has_totals = any(e.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TOTALS for e in existing)
    has_stats = any(e.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATS for e in existing)

    if not has_totals:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "integration_discovery"},
                data={"type": ENTRY_TYPE_TOTALS},
            )
        )
    else:
        async_dispatcher_send(hass, SIGNAL_TOTALS_UPDATE)

    if not has_stats:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "integration_discovery"},
                data={"type": ENTRY_TYPE_STATS},
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type in (ENTRY_TYPE_TOTALS, ENTRY_TYPE_STATS):
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        async_dispatcher_send(hass, SIGNAL_TOTALS_UPDATE)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change (e.g. currency or interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
