"""Sensor platform for Satoshi Sensor."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, CONF_ENTRY_TYPE, CONF_LABEL, DOMAIN, ENTRY_TYPE_XPUB
from .coordinator import SatoshiSensorCoordinator, XpubCoordinator
from .xpub import ADDRESS_TYPES

_AnyCoordinator = SatoshiSensorCoordinator | XpubCoordinator

# (type_key -> type_label) — same order as xpub.ADDRESS_TYPES
_XPUB_TYPE_LABELS = {t[0]: t[1] for t in ADDRESS_TYPES}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: _AnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    label = entry.data[CONF_LABEL]
    is_xpub = entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB

    if is_xpub:
        identifier = entry.data.get("xpub", "")
        entities = []
        for type_key, type_label in _XPUB_TYPE_LABELS.items():
            dev_id = f"{identifier}_{type_key}"
            device = DeviceInfo(
                identifiers={(DOMAIN, dev_id)},
                name=f"BTC Wallet {label} · {type_label}",
                manufacturer="Bitcoin",
                model=f"HD Wallet ({type_label})",
                entry_type=DeviceEntryType.SERVICE,
            )
            uid = f"{DOMAIN}_{identifier[:16]}_{type_key}"
            entities += [
                XpubSatoshiSensor(coordinator, uid, device, type_key),
                XpubBtcSensor(coordinator, uid, device, type_key),
                XpubFiatSensor(coordinator, uid, device, type_key),
                XpubPriceChangeSensor(coordinator, uid, device),
                XpubUnconfirmedSensor(coordinator, uid, device, type_key),
                XpubAddressCountSensor(coordinator, uid, device, type_key),
            ]
        async_add_entities(entities)
    else:
        identifier = entry.data.get(CONF_ADDRESS, "")
        device = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=f"BTC Wallet {label}",
            manufacturer="Bitcoin",
            model="Wallet",
            entry_type=DeviceEntryType.SERVICE,
        )
        async_add_entities([
            SatoshiBalanceSensor(coordinator, entry, identifier, device),
            BtcBalanceSensor(coordinator, entry, identifier, device),
            FiatValueSensor(coordinator, entry, identifier, device),
            PriceChange24hSensor(coordinator, entry, identifier, device),
            UnconfirmedBalanceSensor(coordinator, entry, identifier, device),
        ])


# ── Single-address sensors (flat data structure) ──────────────────────────────

class _BaseSensor(CoordinatorEntity[SatoshiSensorCoordinator], SensorEntity):
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, identifier, device):
        super().__init__(coordinator)
        self._identifier = identifier
        self._attr_device_info = device


class SatoshiBalanceSensor(_BaseSensor):
    _attr_name = "Balance (Satoshi)"
    _attr_native_unit_of_measurement = "sat"
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, entry, identifier, device):
        super().__init__(coordinator, entry, identifier, device)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_satoshi"

    @property
    def native_value(self):
        return self.coordinator.data["satoshi"] if self.coordinator.data else None


class BtcBalanceSensor(_BaseSensor):
    _attr_name = "Balance (BTC)"
    _attr_native_unit_of_measurement = "BTC"
    _attr_suggested_display_precision = 8
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, entry, identifier, device):
        super().__init__(coordinator, entry, identifier, device)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_btc"

    @property
    def native_value(self):
        return self.coordinator.data["btc"] if self.coordinator.data else None


class FiatValueSensor(_BaseSensor):
    _attr_name = "Wert"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:currency-eur"

    def __init__(self, coordinator, entry, identifier, device):
        super().__init__(coordinator, entry, identifier, device)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_fiat"

    @property
    def native_unit_of_measurement(self):
        return self.coordinator.data["currency"] if self.coordinator.data else None

    @property
    def native_value(self):
        return self.coordinator.data["fiat"] if self.coordinator.data else None


class PriceChange24hSensor(_BaseSensor):
    _attr_name = "BTC Preisänderung 24h"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:trending-up"

    def __init__(self, coordinator, entry, identifier, device):
        super().__init__(coordinator, entry, identifier, device)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_price_change_24h"

    @property
    def native_value(self):
        return self.coordinator.data["price_change_24h"] if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        if self.coordinator.data:
            return {"btc_price": self.coordinator.data["price"], "currency": self.coordinator.data["currency"]}
        return {}


class UnconfirmedBalanceSensor(_BaseSensor):
    _attr_name = "Unbestätigtes Guthaben"
    _attr_native_unit_of_measurement = "sat"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, entry, identifier, device):
        super().__init__(coordinator, entry, identifier, device)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_unconfirmed"

    @property
    def native_value(self):
        return self.coordinator.data["unconfirmed_satoshi"] if self.coordinator.data else None


# ── xpub sensors — 3 device groups, data in coordinator.data["types"][type_key] ──

class _XpubBaseSensor(CoordinatorEntity[XpubCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, uid_prefix, device, type_key=None):
        super().__init__(coordinator)
        self._type_key = type_key
        self._attr_device_info = device

    def _type_data(self) -> dict | None:
        if self.coordinator.data and self._type_key:
            return self.coordinator.data["types"].get(self._type_key)
        return None


class XpubSatoshiSensor(_XpubBaseSensor):
    _attr_name = "Balance (Satoshi)"
    _attr_native_unit_of_measurement = "sat"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, uid_prefix, device, type_key):
        super().__init__(coordinator, uid_prefix, device, type_key)
        self._attr_unique_id = f"{uid_prefix}_satoshi"

    @property
    def native_value(self):
        d = self._type_data()
        return d["satoshi"] if d else None

    @property
    def extra_state_attributes(self):
        d = self._type_data()
        return {"addresses": d["addresses"]} if d else {}


class XpubBtcSensor(_XpubBaseSensor):
    _attr_name = "Balance (BTC)"
    _attr_native_unit_of_measurement = "BTC"
    _attr_suggested_display_precision = 8
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, uid_prefix, device, type_key):
        super().__init__(coordinator, uid_prefix, device, type_key)
        self._attr_unique_id = f"{uid_prefix}_btc"

    @property
    def native_value(self):
        d = self._type_data()
        return d["btc"] if d else None


class XpubFiatSensor(_XpubBaseSensor):
    _attr_name = "Wert"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:currency-eur"

    def __init__(self, coordinator, uid_prefix, device, type_key):
        super().__init__(coordinator, uid_prefix, device, type_key)
        self._attr_unique_id = f"{uid_prefix}_fiat"

    @property
    def native_unit_of_measurement(self):
        return self.coordinator.data["currency"] if self.coordinator.data else None

    @property
    def native_value(self):
        d = self._type_data()
        return d["fiat"] if d else None


class XpubPriceChangeSensor(_XpubBaseSensor):
    _attr_name = "BTC Preisänderung 24h"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:trending-up"

    def __init__(self, coordinator, uid_prefix, device):
        super().__init__(coordinator, uid_prefix, device, type_key=None)
        self._attr_unique_id = f"{uid_prefix}_price_change_24h"

    @property
    def native_value(self):
        return self.coordinator.data["price_change_24h"] if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        if self.coordinator.data:
            return {"btc_price": self.coordinator.data["price"], "currency": self.coordinator.data["currency"]}
        return {}


class XpubUnconfirmedSensor(_XpubBaseSensor):
    _attr_name = "Unbestätigtes Guthaben"
    _attr_native_unit_of_measurement = "sat"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, uid_prefix, device, type_key):
        super().__init__(coordinator, uid_prefix, device, type_key)
        self._attr_unique_id = f"{uid_prefix}_unconfirmed"

    @property
    def native_value(self):
        d = self._type_data()
        return d["unconfirmed_satoshi"] if d else None


class XpubAddressCountSensor(_XpubBaseSensor):
    _attr_name = "Aktive Adressen"
    _attr_native_unit_of_measurement = "Adressen"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:wallet"

    def __init__(self, coordinator, uid_prefix, device, type_key):
        super().__init__(coordinator, uid_prefix, device, type_key)
        self._attr_unique_id = f"{uid_prefix}_address_count"

    @property
    def native_value(self):
        d = self._type_data()
        return d["address_count"] if d else None
