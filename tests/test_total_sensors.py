"""Tests for aggregate total sensors."""
import pytest


SATOSHIS_PER_BTC = 100_000_000


def _make_coordinator_data(satoshi: int, price: float, currency: str) -> dict:
    btc = satoshi / SATOSHIS_PER_BTC
    return {
        "satoshi": satoshi,
        "btc": btc,
        "fiat": round(btc * price, 2),
        "currency": currency,
        "price": price,
        "price_change_24h": 0.0,
        "unconfirmed_satoshi": 0,
        "tx_count": 1,
    }


class _FakeCoordinator:
    def __init__(self, data):
        self.data = data


class _FakeTotalSensor:
    """Replicates TotalValueSensor logic without HA deps."""

    def __init__(self, coordinators: list):
        self._coords = coordinators

    def _coordinators(self):
        return [c for c in self._coords if c.data]

    @property
    def total_satoshi(self) -> int:
        return sum(c.data.get("satoshi", 0) for c in self._coordinators())

    @property
    def total_btc(self) -> float:
        return sum(c.data.get("btc", 0.0) for c in self._coordinators())

    @property
    def total_value(self) -> float | None:
        coordinators = self._coordinators()
        if not coordinators:
            return None
        currencies = {c.data["currency"] for c in coordinators}
        if len(currencies) != 1:
            return None
        return round(sum(c.data.get("fiat", 0.0) for c in coordinators), 2)

    @property
    def currency(self) -> str | None:
        coordinators = self._coordinators()
        currencies = {c.data["currency"] for c in coordinators if c.data}
        return currencies.pop() if len(currencies) == 1 else None


class TestTotalSensors:
    def test_single_wallet_satoshi(self):
        c = _FakeCoordinator(_make_coordinator_data(1_000_000, 80000.0, "EUR"))
        sensor = _FakeTotalSensor([c])
        assert sensor.total_satoshi == 1_000_000

    def test_single_wallet_btc(self):
        c = _FakeCoordinator(_make_coordinator_data(100_000_000, 80000.0, "EUR"))
        sensor = _FakeTotalSensor([c])
        assert sensor.total_btc == 1.0

    def test_single_wallet_value(self):
        c = _FakeCoordinator(_make_coordinator_data(100_000_000, 80000.0, "EUR"))
        sensor = _FakeTotalSensor([c])
        assert sensor.total_value == 80000.0
        assert sensor.currency == "EUR"

    def test_two_wallets_satoshi_summed(self):
        c1 = _FakeCoordinator(_make_coordinator_data(500_000, 80000.0, "EUR"))
        c2 = _FakeCoordinator(_make_coordinator_data(300_000, 80000.0, "EUR"))
        sensor = _FakeTotalSensor([c1, c2])
        assert sensor.total_satoshi == 800_000

    def test_two_wallets_btc_summed(self):
        c1 = _FakeCoordinator(_make_coordinator_data(50_000_000, 80000.0, "EUR"))
        c2 = _FakeCoordinator(_make_coordinator_data(50_000_000, 80000.0, "EUR"))
        sensor = _FakeTotalSensor([c1, c2])
        assert sensor.total_btc == pytest.approx(1.0)

    def test_two_wallets_fiat_summed(self):
        c1 = _FakeCoordinator(_make_coordinator_data(100_000_000, 80000.0, "EUR"))
        c2 = _FakeCoordinator(_make_coordinator_data(50_000_000, 80000.0, "EUR"))
        sensor = _FakeTotalSensor([c1, c2])
        assert sensor.total_value == pytest.approx(120000.0)

    def test_mixed_currencies_value_is_none(self):
        c1 = _FakeCoordinator(_make_coordinator_data(100_000_000, 80000.0, "EUR"))
        c2 = _FakeCoordinator(_make_coordinator_data(100_000_000, 90000.0, "USD"))
        sensor = _FakeTotalSensor([c1, c2])
        assert sensor.total_value is None
        assert sensor.currency is None
        # But satoshi/btc still work
        assert sensor.total_satoshi == 200_000_000
        assert sensor.total_btc == pytest.approx(2.0)

    def test_no_coordinators(self):
        sensor = _FakeTotalSensor([])
        assert sensor.total_satoshi == 0
        assert sensor.total_btc == 0.0
        assert sensor.total_value is None
        assert sensor.currency is None

    def test_coordinator_without_data_skipped(self):
        c1 = _FakeCoordinator(_make_coordinator_data(500_000, 80000.0, "EUR"))
        c2 = _FakeCoordinator(None)  # not yet loaded
        sensor = _FakeTotalSensor([c1, c2])
        assert sensor.total_satoshi == 500_000
        assert sensor.currency == "EUR"

    def test_zero_balance_wallet_included(self):
        c1 = _FakeCoordinator(_make_coordinator_data(0, 80000.0, "EUR"))
        c2 = _FakeCoordinator(_make_coordinator_data(1_000_000, 80000.0, "EUR"))
        sensor = _FakeTotalSensor([c1, c2])
        assert sensor.total_satoshi == 1_000_000
