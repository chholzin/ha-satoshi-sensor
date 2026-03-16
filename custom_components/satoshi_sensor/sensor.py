"""Sensor platform for Satoshi Sensor."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ADDRESS, CONF_ENTRY_TYPE, CONF_LABEL, CONF_XPUB,
    DOMAIN, ENTRY_TYPE_TOTALS, ENTRY_TYPE_XPUB, SIGNAL_TOTALS_UPDATE,
)
from .coordinator import SatoshiSensorCoordinator, XpubCoordinator

_AnyCoordinator = SatoshiSensorCoordinator | XpubCoordinator

_XPUB_TYPE_LABEL = {
    "xpub": "Legacy",
    "ypub": "SegWit",
    "zpub": "Native SegWit",
}

_ADDRESS_TYPE_LABEL = {
    "1": "Legacy",
    "3": "SegWit",
    "bc1q": "Native SegWit",
    "bc1p": "Taproot",
}


def _address_type_label(address: str) -> str:
    for prefix, label in _ADDRESS_TYPE_LABEL.items():
        if address.startswith(prefix):
            return label
    return "Wallet"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # Portfolio Total entry — only create aggregate sensors
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TOTALS:
        async_add_entities([
            TotalSatoshiSensor(hass),
            TotalBtcSensor(hass),
            TotalValueSensor(hass),
        ])
        return

    coordinator: _AnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    label = entry.data[CONF_LABEL]
    is_xpub = entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB
    identifier = entry.data.get(CONF_XPUB, entry.data.get(CONF_ADDRESS, ""))

    entities = [
        SatoshiBalanceSensor(coordinator, entry, identifier, label, is_xpub),
        BtcBalanceSensor(coordinator, entry, identifier, label),
        FiatValueSensor(coordinator, entry, identifier, label),
        PriceChange24hSensor(coordinator, entry, identifier, label),
        UnconfirmedBalanceSensor(coordinator, entry, identifier, label),
        TransactionCountSensor(coordinator, entry, identifier, label),
    ]
    if is_xpub:
        entities.append(AddressCountSensor(coordinator, entry, identifier, label))

    async_add_entities(entities)


def _device_info(entry: ConfigEntry, identifier: str, label: str) -> DeviceInfo:
    is_xpub = entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB
    if is_xpub:
        prefix = entry.data.get(CONF_XPUB, "")[:4].lower()
        type_label = _XPUB_TYPE_LABEL.get(prefix, "HD Wallet")
        name = f"BTC Wallet {label} · {type_label}"
        model = f"HD Wallet ({type_label})"
    else:
        type_label = _address_type_label(identifier)
        name = f"BTC Wallet {label} · {type_label}"
        model = f"Wallet ({type_label})"
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        name=name,
        manufacturer="Bitcoin",
        model=model,
        entry_type=DeviceEntryType.SERVICE,
    )


class _BaseSensor(CoordinatorEntity[_AnyCoordinator], SensorEntity):
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _AnyCoordinator,
        entry: ConfigEntry,
        identifier: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._identifier = identifier
        self._label = label
        self._attr_device_info = _device_info(entry, identifier, label)


class SatoshiBalanceSensor(_BaseSensor):
    _attr_name = "Balance (Satoshi)"
    _attr_native_unit_of_measurement = "sat"
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, entry, identifier, label, is_xpub: bool = False):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_satoshi"
        self._is_xpub = is_xpub

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            return self.coordinator.data["satoshi"]
        return None

    @property
    def extra_state_attributes(self) -> dict:
        if self._is_xpub and self.coordinator.data:
            return {"addresses": self.coordinator.data.get("addresses", {})}
        return {}


class BtcBalanceSensor(_BaseSensor):
    _attr_name = "Balance (BTC)"
    _attr_native_unit_of_measurement = "BTC"
    _attr_suggested_display_precision = 8
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_btc"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data["btc"]
        return None


_CURRENCY_ICON = {
    "EUR": "mdi:currency-eur",
    "USD": "mdi:currency-usd",
    "GBP": "mdi:currency-gbp",
}
_DEFAULT_CURRENCY_ICON = "mdi:cash"


class FiatValueSensor(_BaseSensor):
    _attr_name = "Value"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_fiat"

    @property
    def icon(self) -> str:
        if self.coordinator.data:
            return _CURRENCY_ICON.get(
                self.coordinator.data["currency"], _DEFAULT_CURRENCY_ICON
            )
        return _DEFAULT_CURRENCY_ICON

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data["currency"]
        return None

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data["fiat"]
        return None


class PriceChange24hSensor(_BaseSensor):
    _attr_name = "BTC Price Change 24h"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_price_change_24h"

    @property
    def icon(self) -> str:
        if self.coordinator.data and self.coordinator.data.get("price_change_24h", 0) < 0:
            return "mdi:trending-down"
        return "mdi:trending-up"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data["price_change_24h"]
        return None

    @property
    def extra_state_attributes(self) -> dict:
        if self.coordinator.data:
            return {
                "btc_price": self.coordinator.data["price"],
                "currency": self.coordinator.data["currency"],
            }
        return {}


class UnconfirmedBalanceSensor(_BaseSensor):
    _attr_name = "Unconfirmed Balance"
    _attr_native_unit_of_measurement = "sat"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_unconfirmed"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            return self.coordinator.data["unconfirmed_satoshi"]
        return None


class TransactionCountSensor(_BaseSensor):
    _attr_name = "Transactions"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_tx_count"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            return self.coordinator.data.get("tx_count")
        return None


class AddressCountSensor(_BaseSensor):
    _attr_name = "Active Addresses"
    _attr_native_unit_of_measurement = "addresses"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:wallet"

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_address_count"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            return self.coordinator.data.get("address_count")
        return None


# ── Total sensors (aggregate across all config entries) ──────────────────────

_TOTALS_DEVICE = DeviceInfo(
    identifiers={(DOMAIN, "_totals")},
    name="Satoshi Sensor · Total",
    manufacturer="Bitcoin",
    model="Aggregated Wallets",
    entry_type=DeviceEntryType.SERVICE,
)


class _TotalSensor(SensorEntity):
    """Base class for aggregate sensors that sum all wallet coordinators."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL
    _attr_device_info = _TOTALS_DEVICE

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._subscribed_entries: set[str] = set()

    async def async_added_to_hass(self) -> None:
        # Subscribe to dispatcher — fires when entries are added/removed
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_TOTALS_UPDATE, self._on_entries_changed
            )
        )
        # Subscribe to all coordinators already present
        self._subscribe_new_coordinators()

    @callback
    def _on_entries_changed(self) -> None:
        """Called when a wallet entry is added or removed."""
        self._subscribe_new_coordinators()
        self.async_write_ha_state()

    @callback
    def _subscribe_new_coordinators(self) -> None:
        """Subscribe to any coordinator not yet tracked."""
        for key, coordinator in self._hass.data.get(DOMAIN, {}).items():
            if (
                not key.startswith("_")
                and key not in self._subscribed_entries
                and hasattr(coordinator, "async_add_listener")
            ):
                self._subscribed_entries.add(key)
                self.async_on_remove(
                    coordinator.async_add_listener(self._handle_coordinator_update)
                )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Called whenever any wallet coordinator refreshes its data."""
        self.async_write_ha_state()

    def _coordinators(self):
        return [
            c for k, c in self._hass.data.get(DOMAIN, {}).items()
            if not k.startswith("_") and hasattr(c, "data") and c.data
        ]


class TotalSatoshiSensor(_TotalSensor):
    _attr_unique_id = f"{DOMAIN}_total_satoshi"
    _attr_name = "Total Balance (Satoshi)"
    _attr_native_unit_of_measurement = "sat"
    _attr_icon = "mdi:bitcoin"

    @property
    def native_value(self) -> int:
        return sum(c.data.get("satoshi", 0) for c in self._coordinators())


class TotalBtcSensor(_TotalSensor):
    _attr_unique_id = f"{DOMAIN}_total_btc"
    _attr_name = "Total Balance (BTC)"
    _attr_native_unit_of_measurement = "BTC"
    _attr_suggested_display_precision = 8
    _attr_icon = "mdi:bitcoin"

    @property
    def native_value(self) -> float:
        return sum(c.data.get("btc", 0.0) for c in self._coordinators())


class TotalValueSensor(_TotalSensor):
    _attr_unique_id = f"{DOMAIN}_total_value"
    _attr_name = "Total Value"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash-multiple"

    @property
    def native_unit_of_measurement(self) -> str | None:
        coordinators = self._coordinators()
        if not coordinators:
            return None
        currencies = {c.data["currency"] for c in coordinators if c.data}
        return currencies.pop() if len(currencies) == 1 else None

    @property
    def native_value(self) -> float | None:
        coordinators = self._coordinators()
        if not coordinators:
            return None
        currencies = {c.data["currency"] for c in coordinators if c.data}
        if len(currencies) != 1:
            return None  # Mixed currencies — can't sum meaningfully
        return round(sum(c.data.get("fiat", 0.0) for c in coordinators), 2)

    @property
    def extra_state_attributes(self) -> dict:
        coordinators = self._coordinators()
        currencies = {c.data["currency"] for c in coordinators if c.data}
        if len(currencies) > 1:
            return {"warning": f"Mixed currencies detected: {', '.join(sorted(currencies))} — value unavailable"}
        return {}
