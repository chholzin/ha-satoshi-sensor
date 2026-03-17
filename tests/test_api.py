"""Async integration tests for API fetch functions."""
import importlib.util
import os
import sys
import types

import aiohttp
import pytest
from aioresponses import aioresponses

# Stub HA modules so coordinator.py can be imported
_pkg_name = "custom_components.satoshi_sensor"
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules.setdefault(_pkg_name, types.ModuleType(_pkg_name))

_const = types.ModuleType(f"{_pkg_name}.const")
for _k, _v in {
    "COINGECKO_API_URL": (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies={currency}&include_24hr_change=true"
    ),
    "DEFAULT_MEMPOOL_URL": "https://mempool.space/api",
    "DEFAULT_UPDATE_INTERVAL": 300,
    "DOMAIN": "satoshi_sensor",
    "GAP_LIMIT": 20,
    "MIN_UPDATE_INTERVAL": 60,
    "SATOSHIS_PER_BTC": 100_000_000,
    "XPUB_BATCH_SIZE": 20,
    "XPUB_SCAN_TIMEOUT": 600,
    "XPUB_SCAN_TIMEOUT_CUSTOM": 1800,
    "XPUB_CONCURRENCY": 5,
    "XPUB_CONCURRENCY_CUSTOM": 1,
    "CONF_XPUB_CONCURRENCY": "xpub_concurrency",
    "REQUEST_DELAY_CUSTOM": 0.3,
}.items():
    setattr(_const, _k, _v)
sys.modules[f"{_pkg_name}.const"] = _const

_ha_helpers = types.ModuleType("homeassistant.helpers")
_ha_helpers.__path__ = []
for _mod_name, _mod_obj in [
    ("homeassistant", types.ModuleType("homeassistant")),
    ("homeassistant.core", types.ModuleType("homeassistant.core")),
    ("homeassistant.helpers", _ha_helpers),
    ("homeassistant.helpers.update_coordinator", types.ModuleType("homeassistant.helpers.update_coordinator")),
    ("homeassistant.helpers.storage", types.ModuleType("homeassistant.helpers.storage")),
]:
    sys.modules.setdefault(_mod_name, _mod_obj)

_ha_core = sys.modules["homeassistant.core"]
_ha_core.HomeAssistant = object

_ha_storage = sys.modules["homeassistant.helpers.storage"]
_ha_storage.Store = object

_ha_uc = sys.modules["homeassistant.helpers.update_coordinator"]


class _FakeCoordinator:
    pass


class _UpdateFailed(Exception):
    pass


_ha_uc.DataUpdateCoordinator = _FakeCoordinator
_ha_uc.UpdateFailed = _UpdateFailed

_coord_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "satoshi_sensor", "coordinator.py")
_coord_spec = importlib.util.spec_from_file_location(f"{_pkg_name}.coordinator", _coord_path)
_coord_mod = importlib.util.module_from_spec(_coord_spec)
sys.modules[f"{_pkg_name}.coordinator"] = _coord_mod
_coord_spec.loader.exec_module(_coord_mod)

_fetch_price = _coord_mod._fetch_price
_fetch_address_data = _coord_mod._fetch_address_data
import asyncio


MEMPOOL_URL = "https://mempool.space/api"
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=eur&include_24hr_change=true"
)
ADDR = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"


@pytest.fixture
def mock_aiohttp():
    with aioresponses() as m:
        yield m


class TestFetchPrice:
    @pytest.mark.asyncio
    async def test_success(self, mock_aiohttp):
        mock_aiohttp.get(COINGECKO_URL, payload={
            "bitcoin": {"eur": 95000.0, "eur_24h_change": 2.5}
        })
        async with aiohttp.ClientSession() as session:
            price, change = await _fetch_price(session, "eur")
        assert price == 95000.0
        assert change == 2.5

    @pytest.mark.asyncio
    async def test_missing_change_defaults_to_zero(self, mock_aiohttp):
        mock_aiohttp.get(COINGECKO_URL, payload={
            "bitcoin": {"eur": 95000.0}
        })
        async with aiohttp.ClientSession() as session:
            price, change = await _fetch_price(session, "eur")
        assert price == 95000.0
        assert change == 0.0

    @pytest.mark.asyncio
    async def test_http_error_raises(self, mock_aiohttp):
        mock_aiohttp.get(COINGECKO_URL, status=429)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(_UpdateFailed, match="rate limit"):
                await _fetch_price(session, "eur")

    @pytest.mark.asyncio
    async def test_server_error_raises(self, mock_aiohttp):
        mock_aiohttp.get(COINGECKO_URL, status=500)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(_UpdateFailed, match="server error"):
                await _fetch_price(session, "eur")

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, mock_aiohttp):
        mock_aiohttp.get(COINGECKO_URL, body="not json", content_type="text/html")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(_UpdateFailed, match="invalid JSON"):
                await _fetch_price(session, "eur")

    @pytest.mark.asyncio
    async def test_missing_key_raises(self, mock_aiohttp):
        mock_aiohttp.get(COINGECKO_URL, payload={"bitcoin": {}})
        async with aiohttp.ClientSession() as session:
            with pytest.raises(_UpdateFailed, match="Unexpected"):
                await _fetch_price(session, "eur")


class TestFetchAddressData:
    @pytest.mark.asyncio
    async def test_success(self, mock_aiohttp):
        mock_aiohttp.get(f"{MEMPOOL_URL}/address/{ADDR}", payload={
            "chain_stats": {
                "funded_txo_sum": 500_000,
                "spent_txo_sum": 100_000,
                "tx_count": 5,
            },
            "mempool_stats": {
                "funded_txo_sum": 10_000,
                "spent_txo_sum": 0,
            },
        })
        sem = asyncio.Semaphore(1)
        async with aiohttp.ClientSession() as session:
            data = await _fetch_address_data(session, ADDR, sem)
        assert data["balance"] == 400_000
        assert data["unconfirmed"] == 10_000
        assert data["tx_count"] == 5

    @pytest.mark.asyncio
    async def test_http_error(self, mock_aiohttp):
        mock_aiohttp.get(f"{MEMPOOL_URL}/address/{ADDR}", status=429)
        sem = asyncio.Semaphore(1)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(_UpdateFailed, match="rate limit"):
                await _fetch_address_data(session, ADDR, sem)

    @pytest.mark.asyncio
    async def test_custom_mempool_url(self, mock_aiohttp):
        custom_url = "http://umbrel.local:3006/api"
        mock_aiohttp.get(f"{custom_url}/address/{ADDR}", payload={
            "chain_stats": {
                "funded_txo_sum": 100_000,
                "spent_txo_sum": 0,
                "tx_count": 1,
            },
            "mempool_stats": {
                "funded_txo_sum": 0,
                "spent_txo_sum": 0,
            },
        })
        sem = asyncio.Semaphore(1)
        async with aiohttp.ClientSession() as session:
            data = await _fetch_address_data(session, ADDR, sem, custom_url)
        assert data["balance"] == 100_000

    @pytest.mark.asyncio
    async def test_custom_url_500_shows_indexing_hint(self, mock_aiohttp):
        custom_url = "http://umbrel.local:3006/api"
        mock_aiohttp.get(f"{custom_url}/address/{ADDR}", status=500)
        sem = asyncio.Semaphore(1)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(_UpdateFailed, match="indexing"):
                await _fetch_address_data(session, ADDR, sem, custom_url)
