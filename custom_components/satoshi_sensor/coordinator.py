"""DataUpdateCoordinators for Satoshi Sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COINGECKO_API_URL,
    DEFAULT_UPDATE_INTERVAL,
    GAP_LIMIT,
    MEMPOOL_API_URL,
    MIN_UPDATE_INTERVAL,
    SATOSHIS_PER_BTC,
    XPUB_BATCH_SIZE,
)

_LOGGER = logging.getLogger(__name__)


def _classify_http_error(status: int, source: str) -> str:
    if status == 429:
        return f"{source} rate limit exceeded (HTTP 429) — consider increasing the update interval"
    if 500 <= status < 600:
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
) -> dict:
    async with semaphore:
        url = MEMPOOL_API_URL.format(address=address)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise UpdateFailed(_classify_http_error(resp.status, f"mempool.space ({address[:8]}…)"))
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
    ) -> None:
        self.address = address
        self.currency = currency.lower()
        self._session: aiohttp.ClientSession | None = None
        self._base_interval = timedelta(seconds=max(update_interval, MIN_UPDATE_INTERVAL))
        self._consecutive_errors = 0
        super().__init__(
            hass,
            _LOGGER,
            name=f"satoshi_sensor_{address[:8]}",
            update_interval=self._base_interval,
        )

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
            addr_data = await _fetch_address_data(self._session, self.address, semaphore)
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
        return {
            "satoshi": balance_satoshi,
            "btc": balance_btc,
            "fiat": round(balance_btc * price, 2),
            "currency": self.currency.upper(),
            "price": price,
            "price_change_24h": price_change_24h,
            "unconfirmed_satoshi": addr_data["unconfirmed"],
        }

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
    ) -> None:
        self.xpub = xpub
        self.currency = currency.lower()
        self._session: aiohttp.ClientSession | None = None
        self._base_interval = timedelta(seconds=max(update_interval, MIN_UPDATE_INTERVAL))
        self._consecutive_errors = 0
        super().__init__(
            hass,
            _LOGGER,
            name=f"satoshi_sensor_xpub_{xpub[:8]}",
            update_interval=self._base_interval,
        )

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
            try:
                addresses_data = await asyncio.wait_for(
                    self._scan_addresses(self._session), timeout=180
                )
            except asyncio.TimeoutError as err:
                raise UpdateFailed("xpub address scan timed out after 180 s") from err
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

        return {
            "satoshi": total_satoshi,
            "btc": balance_btc,
            "fiat": round(balance_btc * price, 2),
            "currency": self.currency.upper(),
            "price": price,
            "price_change_24h": price_change_24h,
            "unconfirmed_satoshi": total_unconfirmed,
            "address_count": active_count,
            "addresses": {
                addr: d["balance"]
                for addr, d in addresses_data.items()
                if d["tx_count"] > 0
            },
        }

    async def async_shutdown(self) -> None:
        """Close the shared HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        await super().async_shutdown()

    async def _scan_addresses(self, session: aiohttp.ClientSession) -> dict:
        from .xpub import derive_addresses

        semaphore = asyncio.Semaphore(5)
        results: dict[str, dict] = {}
        gap = 0
        index = 0

        while gap < GAP_LIMIT:
            batch = await self.hass.async_add_executor_job(
                derive_addresses, self.xpub, index, XPUB_BATCH_SIZE
            )
            tasks = [_fetch_address_data(session, addr, semaphore) for addr in batch]
            batch_results = await asyncio.gather(*tasks)

            for addr, data in zip(batch, batch_results):
                results[addr] = data
                if data["tx_count"] == 0:
                    gap += 1
                else:
                    gap = 0

                if gap >= GAP_LIMIT:
                    return results

            index += XPUB_BATCH_SIZE

        return results
