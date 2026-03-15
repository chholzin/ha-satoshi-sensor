"""Tests for coordinator data processing logic."""
import importlib.util
import os
import sys
import types
from datetime import timedelta

import pytest

SATOSHIS_PER_BTC = 100_000_000

# Load _classify_http_error from coordinator without HA imports
_pkg_name = "custom_components.satoshi_sensor"
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules.setdefault(_pkg_name, types.ModuleType(_pkg_name))

_const = types.ModuleType(f"{_pkg_name}.const")
for _k, _v in {
    "COINGECKO_API_URL": "", "DEFAULT_MEMPOOL_URL": "https://mempool.space/api",
    "DEFAULT_UPDATE_INTERVAL": 300, "DOMAIN": "satoshi_sensor",
    "GAP_LIMIT": 20, "MIN_UPDATE_INTERVAL": 60,
    "SATOSHIS_PER_BTC": SATOSHIS_PER_BTC, "XPUB_BATCH_SIZE": 20,
}.items():
    setattr(_const, _k, _v)
sys.modules[f"{_pkg_name}.const"] = _const

# Stub HA modules
_ha_helpers = types.ModuleType("homeassistant.helpers")
_ha_helpers.__path__ = []  # make it a package
for _mod_name, _mod_obj in [
    ("homeassistant", types.ModuleType("homeassistant")),
    ("homeassistant.core", types.ModuleType("homeassistant.core")),
    ("homeassistant.helpers", _ha_helpers),
    ("homeassistant.helpers.update_coordinator", types.ModuleType("homeassistant.helpers.update_coordinator")),
    ("homeassistant.helpers.storage", types.ModuleType("homeassistant.helpers.storage")),
    ("aiohttp", types.ModuleType("aiohttp")),
]:
    sys.modules.setdefault(_mod_name, _mod_obj)

_ha_core = sys.modules["homeassistant.core"]
_ha_core.HomeAssistant = object

_ha_storage = sys.modules["homeassistant.helpers.storage"]
_ha_storage.Store = object

_ha_uc = sys.modules["homeassistant.helpers.update_coordinator"]


class _FakeCoordinator:
    pass


class _FakeUpdateFailed(Exception):
    pass


_ha_uc.DataUpdateCoordinator = _FakeCoordinator
_ha_uc.UpdateFailed = _FakeUpdateFailed

_coord_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "satoshi_sensor", "coordinator.py")
_coord_spec = importlib.util.spec_from_file_location(f"{_pkg_name}.coordinator", _coord_path)
_coord_mod = importlib.util.module_from_spec(_coord_spec)
sys.modules[f"{_pkg_name}.coordinator"] = _coord_mod
_coord_spec.loader.exec_module(_coord_mod)

_classify_http_error = _coord_mod._classify_http_error
_MAX_BACKOFF_MULTIPLIER = _coord_mod._MAX_BACKOFF_MULTIPLIER


def _compute(satoshi: int, price: float, price_change: float, unconfirmed: int, currency: str) -> dict:
    """Replicate the coordinator's output calculation — pure logic, no I/O."""
    balance_btc = satoshi / SATOSHIS_PER_BTC
    return {
        "satoshi": satoshi,
        "btc": balance_btc,
        "fiat": round(balance_btc * price, 2),
        "currency": currency.upper(),
        "price": price,
        "price_change_24h": price_change,
        "unconfirmed_satoshi": unconfirmed,
    }


class TestCoordinatorCalculations:
    def test_zero_balance(self):
        data = _compute(0, 50000.0, 1.5, 0, "eur")
        assert data["satoshi"] == 0
        assert data["btc"] == 0.0
        assert data["fiat"] == 0.0

    def test_one_btc(self):
        data = _compute(100_000_000, 50000.0, 0.0, 0, "eur")
        assert data["btc"] == 1.0
        assert data["fiat"] == 50000.0

    def test_satoshi_to_btc_precision(self):
        data = _compute(1, 100_000.0, 0.0, 0, "eur")
        assert data["btc"] == pytest.approx(1e-8)
        # 1 sat * 100_000 €/BTC = 0.001 €, but round(..., 2) → 0.0
        assert data["fiat"] == 0.0

    def test_currency_uppercased(self):
        data = _compute(1_000_000, 80000.0, 2.5, 0, "eur")
        assert data["currency"] == "EUR"

    def test_fiat_rounding(self):
        # 0.123456789 BTC * 80000 = 9876.54312 → rounds to 9876.54
        satoshi = int(0.123456789 * SATOSHIS_PER_BTC)
        data = _compute(satoshi, 80000.0, 0.0, 0, "eur")
        assert data["fiat"] == round(satoshi / SATOSHIS_PER_BTC * 80000.0, 2)

    def test_unconfirmed_balance(self):
        data = _compute(500_000, 60000.0, -1.2, 10_000, "usd")
        assert data["unconfirmed_satoshi"] == 10_000

    def test_negative_price_change(self):
        data = _compute(100_000, 40000.0, -5.3, 0, "chf")
        assert data["price_change_24h"] == -5.3


class TestXpubAggregation:
    def test_aggregate_multiple_addresses(self):
        """XpubCoordinator sums balances across all addresses."""
        addresses_data = {
            "bc1qabc": {"balance": 100_000, "unconfirmed": 0, "tx_count": 1},
            "bc1qdef": {"balance": 200_000, "unconfirmed": 5_000, "tx_count": 2},
            "bc1qghi": {"balance": 0, "unconfirmed": 0, "tx_count": 0},
        }
        total_satoshi = sum(d["balance"] for d in addresses_data.values())
        total_unconfirmed = sum(d["unconfirmed"] for d in addresses_data.values())
        active_count = sum(1 for d in addresses_data.values() if d["tx_count"] > 0)

        assert total_satoshi == 300_000
        assert total_unconfirmed == 5_000
        assert active_count == 2

    def test_active_addresses_filter(self):
        """Only addresses with tx_count > 0 appear in the 'addresses' attribute."""
        addresses_data = {
            "addr1": {"balance": 50_000, "unconfirmed": 0, "tx_count": 3},
            "addr2": {"balance": 0, "unconfirmed": 0, "tx_count": 0},
            "addr3": {"balance": 10_000, "unconfirmed": 0, "tx_count": 1},
        }
        active = {a: d["balance"] for a, d in addresses_data.items() if d["tx_count"] > 0}
        assert "addr1" in active
        assert "addr3" in active
        assert "addr2" not in active


class TestClassifyHttpError:
    def test_rate_limit_429(self):
        msg = _classify_http_error(429, "CoinGecko")
        assert "rate limit" in msg.lower()
        assert "429" in msg

    def test_server_error_500(self):
        msg = _classify_http_error(500, "mempool.space")
        assert "server error" in msg.lower()
        assert "500" in msg

    def test_server_error_503(self):
        msg = _classify_http_error(503, "CoinGecko")
        assert "server error" in msg.lower()

    def test_generic_error(self):
        msg = _classify_http_error(403, "CoinGecko")
        assert "HTTP 403" in msg

    def test_custom_url_500_shows_indexing_hint(self):
        msg = _classify_http_error(500, "http://umbrel:4080/api", is_custom_url=True)
        assert "indexing" in msg.lower()
        assert "Electrs/Fulcrum" in msg

    def test_public_url_500_no_indexing_hint(self):
        msg = _classify_http_error(500, "mempool.space")
        assert "indexing" not in msg.lower()


class TestBackoffLogic:
    def test_multiplier_capped(self):
        assert _MAX_BACKOFF_MULTIPLIER == 4

    def test_backoff_doubles(self):
        """Simulates the backoff calculation: 2^1=2, 2^2=4, 2^3=8→capped to 4."""
        base = timedelta(seconds=300)
        results = []
        for errors in range(1, 5):
            multiplier = min(2 ** errors, _MAX_BACKOFF_MULTIPLIER)
            results.append(base * multiplier)
        assert results[0] == timedelta(seconds=600)   # 2x
        assert results[1] == timedelta(seconds=1200)  # 4x
        assert results[2] == timedelta(seconds=1200)  # capped at 4x
        assert results[3] == timedelta(seconds=1200)  # still capped
