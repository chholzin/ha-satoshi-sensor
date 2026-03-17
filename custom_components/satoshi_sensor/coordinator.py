"""DataUpdateCoordinators for Satoshi Sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from functools import partial

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COINGECKO_API_URL,
    CONF_XPUB_CONCURRENCY,
    DEFAULT_MEMPOOL_URL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    GAP_LIMIT,
    MIN_UPDATE_INTERVAL,
    REQUEST_DELAY_CUSTOM,
    REQUEST_DELAY_PUBLIC,
    SATOSHIS_PER_BTC,
    XPUB_BATCH_SIZE,
    XPUB_CONCURRENCY,
    XPUB_CONCURRENCY_CUSTOM,
    XPUB_SCAN_TIMEOUT,
    XPUB_SCAN_TIMEOUT_CUSTOM,
)

_STORAGE_VERSION = 1

_LOGGER = logging.getLogger(__name__)


def _classify_http_error(status: int, source: str, *, is_custom_url: bool = False) -> str:
    if status == 429:
        return f"{source} rate limit exceeded (HTTP 429) — consider increasing the update interval"
    if 500 <= status < 600:
        if is_custom_url:
            return (
                f"{source} server error (HTTP {status}) — your Mempool instance "
                "may still be indexing addresses. Check that the Electrum backend "
                "(Electrs/Fulcrum) is fully synced and the address index is enabled."
            )
        return f"{source} server error (HTTP {status}) — the API may be temporarily unavailable"
    return f"{source} returned HTTP {status}"


async def _fetch_price(session: aiohttp.ClientSession, currency: str) -> tuple[float, float]:
    url = COINGECKO_API_URL.format(currency=currency)
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status != 200:
            raise UpdateFailed(_classify_http_error(resp.status, "CoinGecko"))
        try:
            data = await resp.json()
        except (ValueError, aiohttp.ContentTypeError) as err:
            raise UpdateFailed(f"CoinGecko returned invalid JSON: {err}") from err

    try:
        price = data["bitcoin"][currency]
    except (KeyError, TypeError) as err:
        raise UpdateFailed(f"Unexpected CoinGecko response structure: {err}") from err

    change_key = f"{currency}_24h_change"
    price_change_24h = round(data["bitcoin"].get(change_key, 0.0), 2)
    return price, price_change_24h


async def _fetch_address_data(
    session: aiohttp.ClientSession,
    address: str,
    semaphore: asyncio.Semaphore,
    mempool_base_url: str = DEFAULT_MEMPOOL_URL,
) -> dict:
    async with semaphore:
        url = f"{mempool_base_url.rstrip('/')}/address/{address}"
        is_custom = mempool_base_url != DEFAULT_MEMPOOL_URL
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                label = mempool_base_url if is_custom else "mempool.space"
                raise UpdateFailed(
                    _classify_http_error(resp.status, f"{label} ({address[:8]}…)", is_custom_url=is_custom)
                )
            try:
                data = await resp.json()
            except (ValueError, aiohttp.ContentTypeError) as err:
                raise UpdateFailed(f"mempool.space returned invalid JSON for {address}: {err}") from err

    try:
        funded = data["chain_stats"]["funded_txo_sum"]
        spent = data["chain_stats"]["spent_txo_sum"]
        unconfirmed_funded = data["mempool_stats"]["funded_txo_sum"]
        unconfirmed_spent = data["mempool_stats"]["spent_txo_sum"]
        tx_count = data["chain_stats"]["tx_count"]
    except (KeyError, TypeError) as err:
        raise UpdateFailed(f"Unexpected mempool.space response structure for {address}: {err}") from err

    return {
        "balance": funded - spent,
        "unconfirmed": unconfirmed_funded - unconfirmed_spent,
        "tx_count": tx_count,
    }


_MAX_BACKOFF_MULTIPLIER = 4


class SatoshiSensorCoordinator(DataUpdateCoordinator):
    """Fetch data for a single BTC address."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        currency: str,
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
        mempool_url: str = DEFAULT_MEMPOOL_URL,
    ) -> None:
        self.address = address
        self.currency = currency.lower()
        self._mempool_url = mempool_url
        self._session: aiohttp.ClientSession | None = None
        self._base_interval = timedelta(seconds=max(update_interval, MIN_UPDATE_INTERVAL))
        self._consecutive_errors = 0
        self._data_store = Store(hass, _STORAGE_VERSION, f"{DOMAIN}_data_{address[:32]}")
        super().__init__(
            hass,
            _LOGGER,
            name=f"satoshi_sensor_{address[:8]}",
            update_interval=self._base_interval,
        )

    async def async_restore_last_data(self) -> bool:
        """Restore last persisted data. Returns True if data was available."""
        stored = await self._data_store.async_load()
        if stored and isinstance(stored, dict) and "satoshi" in stored:
            self.async_set_updated_data(stored)
            _LOGGER.debug("Restored cached sensor data for %s", self.address[:8])
            return True
        return False

    def _apply_backoff(self) -> None:
        self._consecutive_errors += 1
        multiplier = min(2 ** self._consecutive_errors, _MAX_BACKOFF_MULTIPLIER)
        self.update_interval = self._base_interval * multiplier
        _LOGGER.warning(
            "Update failed (%s consecutive errors), next retry in %s",
            self._consecutive_errors,
            self.update_interval,
        )

    def _reset_backoff(self) -> None:
        if self._consecutive_errors > 0:
            self._consecutive_errors = 0
            self.update_interval = self._base_interval

    async def _async_update_data(self) -> dict:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        try:
            semaphore = asyncio.Semaphore(1)
            addr_data = await _fetch_address_data(self._session, self.address, semaphore, self._mempool_url)
            price, price_change_24h = await _fetch_price(self._session, self.currency)
        except aiohttp.ClientError as err:
            self._apply_backoff()
            raise UpdateFailed(f"Network error: {err}") from err
        except UpdateFailed:
            self._apply_backoff()
            raise

        self._reset_backoff()
        balance_satoshi = addr_data["balance"]
        balance_btc = balance_satoshi / SATOSHIS_PER_BTC
        _LOGGER.debug(
            "Updated %s: %d sat (%.8f BTC), price %.2f %s",
            self.address[:8], balance_satoshi, balance_btc, price, self.currency.upper(),
        )
        result = {
            "satoshi": balance_satoshi,
            "btc": balance_btc,
            "fiat": round(balance_btc * price, 2),
            "currency": self.currency.upper(),
            "price": price,
            "price_change_24h": price_change_24h,
            "unconfirmed_satoshi": addr_data["unconfirmed"],
            "tx_count": addr_data["tx_count"],
        }
        await self._data_store.async_save(result)
        return result

    async def async_shutdown(self) -> None:
        """Close the shared HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        await super().async_shutdown()


class XpubCoordinator(DataUpdateCoordinator):
    """Scan all addresses derived from an xpub/ypub/zpub."""

    def __init__(
        self,
        hass: HomeAssistant,
        xpub: str,
        currency: str,
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
        mempool_url: str = DEFAULT_MEMPOOL_URL,
        concurrency: int | None = None,
    ) -> None:
        self.xpub = xpub
        self.currency = currency.lower()
        self._mempool_url = mempool_url
        self._concurrency = concurrency
        self._session: aiohttp.ClientSession | None = None
        self._base_interval = timedelta(seconds=max(update_interval, MIN_UPDATE_INTERVAL))
        self._consecutive_errors = 0
        self._cached_addresses: list[str] | None = None
        self._store = Store(hass, _STORAGE_VERSION, f"{DOMAIN}_xpub_{xpub[:16]}")
        self._data_store = Store(hass, _STORAGE_VERSION, f"{DOMAIN}_data_xpub_{xpub[:32]}")
        super().__init__(
            hass,
            _LOGGER,
            name=f"satoshi_sensor_xpub_{xpub[:8]}",
            update_interval=self._base_interval,
        )

    async def async_restore_last_data(self) -> bool:
        """Restore last persisted data. Returns True if data was available."""
        stored = await self._data_store.async_load()
        if stored and isinstance(stored, dict) and "satoshi" in stored:
            self.async_set_updated_data(stored)
            _LOGGER.debug("Restored cached sensor data for xpub %s", self.xpub[:8])
            return True
        return False

    def _apply_backoff(self) -> None:
        self._consecutive_errors += 1
        multiplier = min(2 ** self._consecutive_errors, _MAX_BACKOFF_MULTIPLIER)
        self.update_interval = self._base_interval * multiplier
        _LOGGER.warning(
            "Update failed (%s consecutive errors), next retry in %s",
            self._consecutive_errors,
            self.update_interval,
        )

    def _reset_backoff(self) -> None:
        if self._consecutive_errors > 0:
            self._consecutive_errors = 0
            self.update_interval = self._base_interval

    async def _async_update_data(self) -> dict:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        is_custom = self._mempool_url != DEFAULT_MEMPOOL_URL
        timeout = XPUB_SCAN_TIMEOUT_CUSTOM if is_custom else XPUB_SCAN_TIMEOUT
        try:
            try:
                addresses_data = await asyncio.wait_for(
                    self._scan_addresses(self._session, is_custom), timeout=timeout
                )
            except asyncio.TimeoutError as err:
                raise UpdateFailed(
                    f"xpub address scan timed out after {timeout} s"
                ) from err
            price, price_change_24h = await _fetch_price(self._session, self.currency)
        except aiohttp.ClientError as err:
            self._apply_backoff()
            raise UpdateFailed(f"Network error: {err}") from err
        except UpdateFailed:
            self._apply_backoff()
            raise

        self._reset_backoff()
        total_satoshi = sum(d["balance"] for d in addresses_data.values())
        total_unconfirmed = sum(d["unconfirmed"] for d in addresses_data.values())
        balance_btc = total_satoshi / SATOSHIS_PER_BTC
        active_count = sum(1 for d in addresses_data.values() if d["tx_count"] > 0)
        total_tx_count = sum(d["tx_count"] for d in addresses_data.values())

        _LOGGER.debug(
            "Updated xpub %s: %d active addresses, %d sat (%.8f BTC), price %.2f %s",
            self.xpub[:8], active_count, total_satoshi, balance_btc, price, self.currency.upper(),
        )
        result = {
            "satoshi": total_satoshi,
            "btc": balance_btc,
            "fiat": round(balance_btc * price, 2),
            "currency": self.currency.upper(),
            "price": price,
            "price_change_24h": price_change_24h,
            "unconfirmed_satoshi": total_unconfirmed,
            "tx_count": total_tx_count,
            "address_count": active_count,
            "addresses": {
                addr: d["balance"]
                for addr, d in addresses_data.items()
                if d["tx_count"] > 0
            },
        }
        await self._data_store.async_save(result)
        return result

    async def async_shutdown(self) -> None:
        """Close the shared HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        await super().async_shutdown()

    async def _load_cached_addresses(self) -> dict[str, list[str]] | None:
        if self._cached_addresses is not None:
            return self._cached_addresses
        stored = await self._store.async_load()
        if stored and isinstance(stored.get("external"), list):
            self._cached_addresses = {
                "external": stored["external"],
                "change": stored.get("change", []),
            }
            total = len(self._cached_addresses["external"]) + len(self._cached_addresses["change"])
            _LOGGER.debug("Loaded %d cached addresses for %s", total, self.xpub[:8])
            return self._cached_addresses
        # Migrate old format (flat list = external only)
        if stored and isinstance(stored.get("addresses"), list):
            self._cached_addresses = {"external": stored["addresses"], "change": []}
            return self._cached_addresses
        return None

    async def _save_cached_addresses(self, addresses: dict[str, list[str]]) -> None:
        self._cached_addresses = addresses
        await self._store.async_save(addresses)

    async def _scan_chain(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        chain: int,
        fetch_addrs: list[str],
        scan_from_index: int,
        request_delay: float = 0.0,
    ) -> dict[str, dict]:
        """Fetch fetch_addrs and scan for new addresses starting at scan_from_index."""
        from .xpub import derive_addresses

        results: dict[str, dict] = {}

        async def fetch_one(addr: str) -> dict:
            result = await _fetch_address_data(session, addr, semaphore, self._mempool_url)
            if request_delay > 0:
                await asyncio.sleep(request_delay)
            return result

        # Re-fetch the provided addresses (active ones on refresh, all on first scan)
        if fetch_addrs:
            batch_results = await asyncio.gather(*[fetch_one(a) for a in fetch_addrs])
            for addr, data in zip(fetch_addrs, batch_results):
                results[addr] = data

        # Scan beyond scan_from_index for new addresses
        gap = 0
        index = scan_from_index

        while gap < GAP_LIMIT:
            batch = await self.hass.async_add_executor_job(
                partial(derive_addresses, self.xpub, index, XPUB_BATCH_SIZE, chain=chain)
            )
            batch_results = await asyncio.gather(*[fetch_one(a) for a in batch])

            for addr, data in zip(batch, batch_results):
                results[addr] = data
                if data["tx_count"] == 0:
                    gap += 1
                else:
                    gap = 0
                if gap >= GAP_LIMIT:
                    break

            index += XPUB_BATCH_SIZE

        return results

    async def _scan_addresses(self, session: aiohttp.ClientSession, is_custom: bool = False) -> dict:
        if self._concurrency is not None:
            concurrency = self._concurrency
        else:
            concurrency = XPUB_CONCURRENCY_CUSTOM if is_custom else XPUB_CONCURRENCY
        semaphore = asyncio.Semaphore(concurrency)
        request_delay = REQUEST_DELAY_CUSTOM if is_custom else REQUEST_DELAY_PUBLIC

        cached = await self._load_cached_addresses()
        cached_ext = cached["external"] if cached else []
        cached_chg = cached["change"] if cached else []

        # On refresh: only re-fetch known active addresses to reduce API calls.
        # Empty addresses cannot gain a balance — skip them.
        # On first scan (no previous data): fetch all cached addresses.
        if self.data:
            active_addrs = set(self.data.get("addresses", {}).keys())
            fetch_ext = [a for a in cached_ext if a in active_addrs]
            fetch_chg = [a for a in cached_chg if a in active_addrs]
            _LOGGER.debug(
                "xpub %s refresh: %d/%d ext + %d/%d chg active addresses fetched",
                self.xpub[:8],
                len(fetch_ext), len(cached_ext),
                len(fetch_chg), len(cached_chg),
            )
        else:
            fetch_ext = cached_ext
            fetch_chg = cached_chg

        ext_results = await self._scan_chain(
            session, semaphore, 0, fetch_ext, len(cached_ext), request_delay
        )
        chg_results = await self._scan_chain(
            session, semaphore, 1, fetch_chg, len(cached_chg), request_delay
        )

        # Inactive (balance=0, tx_count=0) addresses contribute nothing to totals —
        # omitting them on refresh is correct and saves API calls.
        results = {**ext_results, **chg_results}

        # Update cache: preserve all known addresses, append newly discovered ones
        new_ext = list(dict.fromkeys(cached_ext + [a for a in ext_results if a not in cached_ext]))
        new_chg = list(dict.fromkeys(cached_chg + [a for a in chg_results if a not in cached_chg]))
        new_cache = {"external": new_ext, "change": new_chg}
        if new_cache != (cached or {}):
            await self._save_cached_addresses(new_cache)

        return results
