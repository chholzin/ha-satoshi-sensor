"""DataUpdateCoordinator for Satoshi Sensor."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COINGECKO_API_URL,
    DEFAULT_UPDATE_INTERVAL,
    MEMPOOL_API_URL,
    SATOSHIS_PER_BTC,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class SatoshiSensorCoordinator(DataUpdateCoordinator):
    """Fetch BTC balance and price data."""

    def __init__(
        self, hass: HomeAssistant, address: str, currency: str, update_interval: int = DEFAULT_UPDATE_INTERVAL
    ) -> None:
        self.address = address
        self.currency = currency.lower()
        interval = max(update_interval, MIN_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"satoshi_sensor_{address[:8]}",
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                balance_satoshi = await self._fetch_balance(session)
                price = await self._fetch_price(session)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error: {err}") from err

        balance_btc = balance_satoshi / SATOSHIS_PER_BTC
        fiat_value = round(balance_btc * price, 2)

        return {
            "satoshi": balance_satoshi,
            "btc": balance_btc,
            "fiat": fiat_value,
            "currency": self.currency.upper(),
            "price": price,
        }

    async def _fetch_balance(self, session: aiohttp.ClientSession) -> int:
        url = MEMPOOL_API_URL.format(address=self.address)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"mempool.space returned HTTP {resp.status}")
            data = await resp.json()

        funded = data["chain_stats"]["funded_txo_sum"]
        spent = data["chain_stats"]["spent_txo_sum"]
        return funded - spent

    async def _fetch_price(self, session: aiohttp.ClientSession) -> float:
        url = COINGECKO_API_URL.format(currency=self.currency)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"CoinGecko returned HTTP {resp.status}")
            data = await resp.json()

        return data["bitcoin"][self.currency]
