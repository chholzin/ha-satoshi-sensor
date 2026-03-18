"""Tests for config_flow validation helpers."""
import importlib.util
import sys
import os
import types
import pytest

# Stubs so config_flow.py can be imported without HA
_pkg_name = "custom_components.satoshi_sensor"
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules.setdefault(_pkg_name, types.ModuleType(_pkg_name))

_const = types.ModuleType(f"{_pkg_name}.const")
_const.CONF_ADDRESS = "address"
_const.CONF_CURRENCY = "currency"
_const.CONF_ENTRY_TYPE = "entry_type"
_const.CONF_LABEL = "label"
_const.CONF_MEMPOOL_URL = "mempool_url"
_const.CONF_SCAN_INTERVAL = "scan_interval"
_const.CONF_XPUB = "xpub"
_const.DEFAULT_CURRENCY = "eur"
_const.DEFAULT_MEMPOOL_URL = "https://mempool.space/api"
_const.DEFAULT_UPDATE_INTERVAL = 300
_const.DOMAIN = "satoshi_sensor"
_const.ENTRY_TYPE_ADDRESS = "address"
_const.ENTRY_TYPE_XPUB = "xpub"
_const.ENTRY_TYPE_TOTALS = "totals"
_const.TOTALS_UNIQUE_ID = "satoshi_sensor_totals"
_const.MIN_UPDATE_INTERVAL = 60
_const.SUPPORTED_CURRENCIES = ["eur", "usd", "chf"]
_const.XPUB_PREFIXES = ("xpub", "ypub", "zpub")
_const.CONF_XPUB_CONCURRENCY = "xpub_concurrency"
_const.XPUB_CONCURRENCY = 5
_const.ENTRY_TYPE_STATS = "stats"
_const.STATS_UNIQUE_ID = "satoshi_sensor_stats"
sys.modules[f"{_pkg_name}.const"] = _const

# Stub xpub module (b58check_decode used by _validate_btc_address)
_xpub_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "satoshi_sensor", "xpub.py")
_xpub_spec = importlib.util.spec_from_file_location(f"{_pkg_name}.xpub", _xpub_path)
_xpub_mod = importlib.util.module_from_spec(_xpub_spec)
sys.modules[f"{_pkg_name}.xpub"] = _xpub_mod
_xpub_spec.loader.exec_module(_xpub_mod)

# Stub voluptuous and HA modules
import types as _types
_vol = _types.ModuleType("voluptuous")
_vol.Schema = lambda s: s
_vol.Required = lambda k, **kw: k
_vol.Optional = lambda k, **kw: k
_vol.In = lambda v: v
_vol.All = lambda *a: a[0]
_vol.Range = lambda **kw: None
sys.modules["voluptuous"] = _vol
for _mod in [
    "homeassistant", "homeassistant.config_entries",
    "homeassistant.data_entry_flow",
]:
    sys.modules.setdefault(_mod, _types.ModuleType(_mod))

_ha_ce = sys.modules["homeassistant.config_entries"]
class _ConfigFlowBase:
    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

_ha_ce.ConfigFlow = _ConfigFlowBase
_ha_ce.OptionsFlow = object
_ha_ce.ConfigEntry = object
_ha_ce.ConfigFlowResult = dict

_cf_path = os.path.join(os.path.dirname(__file__), "..", "custom_components", "satoshi_sensor", "config_flow.py")
_cf_spec = importlib.util.spec_from_file_location(f"{_pkg_name}.config_flow", _cf_path)
_cf_mod = importlib.util.module_from_spec(_cf_spec)
sys.modules[f"{_pkg_name}.config_flow"] = _cf_mod
_cf_spec.loader.exec_module(_cf_mod)

_validate_btc_address = _cf_mod._validate_btc_address
_validate_xpub = _cf_mod._validate_xpub


class TestValidateBtcAddress:
    def test_valid_p2pkh(self):
        # Well-known genesis coinbase address
        assert _validate_btc_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf Na") is False
        assert _validate_btc_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True

    def test_valid_p2sh(self):
        assert _validate_btc_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") is True

    def test_valid_bech32(self):
        assert _validate_btc_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq") is True

    def test_invalid_prefix(self):
        assert _validate_btc_address("2A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is False

    def test_too_short(self):
        assert _validate_btc_address("1short") is False

    def test_empty(self):
        assert _validate_btc_address("") is False

    def test_bech32_uppercase_rejected(self):
        assert _validate_btc_address("BC1QAR0SRRR7XFKVY5L643LYDNW9RE59GTZZWF5MDQ") is False

    def test_bad_checksum_legacy(self):
        # Flip last char of genesis address — checksum should fail
        assert _validate_btc_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb") is False

    def test_xpub_not_address(self):
        assert _validate_btc_address("xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKp") is False


class TestValidateXpub:
    def test_xpub_prefix(self):
        assert _validate_xpub("xpub" + "a" * 100) is True

    def test_zpub_prefix(self):
        assert _validate_xpub("zpub" + "a" * 100) is True

    def test_ypub_prefix(self):
        assert _validate_xpub("ypub" + "a" * 100) is True

    def test_too_short(self):
        assert _validate_xpub("xpub123") is False

    def test_invalid_prefix(self):
        assert _validate_xpub("apub" + "a" * 100) is False
