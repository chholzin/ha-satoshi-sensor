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

_AnyCoordinator = SatoshiSensorCoordinator | XpubCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: _AnyCoordinator = hass.data[DOMAIN][entry.entry_id]
    label = entry.data[CONF_LABEL]
    is_xpub = entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB
    identifier = entry.data.get("xpub", entry.data.get(CONF_ADDRESS, ""))

    entities = [
        SatoshiBalanceSensor(coordinator, entry, identifier, label, is_xpub),
        BtcBalanceSensor(coordinator, entry, identifier, label),
        FiatValueSensor(coordinator, entry, identifier, label),
        PriceChange24hSensor(coordinator, entry, identifier, label),
        UnconfirmedBalanceSensor(coordinator, entry, identifier, label),
    ]
    if is_xpub:
        entities.append(AddressCountSensor(coordinator, entry, identifier, label))

    async_add_entities(entities)


def _device_info(entry: ConfigEntry, identifier: str, label: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        name=f"BTC Wallet {label}",
        manufacturer="Bitcoin",
        model="HD Wallet" if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_XPUB else "Wallet",
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


class FiatValueSensor(_BaseSensor):
    _attr_name = "Wert"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:currency-eur"

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_fiat"

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
    _attr_name = "BTC Preisänderung 24h"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:trending-up"

    def __init__(self, coordinator, entry, identifier, label):
        super().__init__(coordinator, entry, identifier, label)
        self._attr_unique_id = f"{DOMAIN}_{identifier}_price_change_24h"

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
    _attr_name = "Unbestätigtes Guthaben"
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


class AddressCountSensor(_BaseSensor):
    _attr_name = "Aktive Adressen"
    _attr_native_unit_of_measurement = "Adressen"
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
