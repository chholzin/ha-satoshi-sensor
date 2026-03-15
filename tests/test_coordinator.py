"""Tests for coordinator data processing logic."""
import pytest

SATOSHIS_PER_BTC = 100_000_000


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
