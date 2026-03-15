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

from .const import CONF_ADDRESS, CONF_LABEL, DOMAIN
from .coordinator import SatoshiSensorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SatoshiSensorCoordinator = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    label = entry.data[CONF_LABEL]

    async_add_entities(
        [
            SatoshiBalanceSensor(coordinator, entry, address, label),
            BtcBalanceSensor(coordinator, entry, address, label),
            FiatValueSensor(coordinator, entry, address, label),
            PriceChange24hSensor(coordinator, entry, address, label),
        ]
    )


def _device_info(entry: ConfigEntry, address: str, label: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, address)},
        name=f"BTC Wallet {label}",
        manufacturer="Bitcoin",
        model="Wallet",
        entry_type=DeviceEntryType.SERVICE,
    )


class _BaseSensor(CoordinatorEntity[SatoshiSensorCoordinator], SensorEntity):
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SatoshiSensorCoordinator,
        entry: ConfigEntry,
        address: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._address = address
        self._label = label
        self._attr_device_info = _device_info(entry, address, label)


class SatoshiBalanceSensor(_BaseSensor):
    _attr_name = "Balance (Satoshi)"
    _attr_native_unit_of_measurement = "sat"
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, entry, address, label):
        super().__init__(coordinator, entry, address, label)
        self._attr_unique_id = f"{DOMAIN}_{address}_satoshi"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            return self.coordinator.data["satoshi"]
        return None


class BtcBalanceSensor(_BaseSensor):
    _attr_name = "Balance (BTC)"
    _attr_native_unit_of_measurement = "BTC"
    _attr_suggested_display_precision = 8
    _attr_icon = "mdi:bitcoin"

    def __init__(self, coordinator, entry, address, label):
        super().__init__(coordinator, entry, address, label)
        self._attr_unique_id = f"{DOMAIN}_{address}_btc"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data["btc"]
        return None


class PriceChange24hSensor(_BaseSensor):
    _attr_name = "BTC Preisänderung 24h"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:trending-up"

    def __init__(self, coordinator, entry, address, label):
        super().__init__(coordinator, entry, address, label)
        self._attr_unique_id = f"{DOMAIN}_{address}_price_change_24h"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data["price_change_24h"]
        return None

    @property
    def extra_state_attributes(self) -> dict:
        if self.coordinator.data:
            return {"btc_price": self.coordinator.data["price"], "currency": self.coordinator.data["currency"]}
        return {}


class FiatValueSensor(_BaseSensor):
    _attr_name = "Wert"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:currency-eur"

    def __init__(self, coordinator, entry, address, label):
        super().__init__(coordinator, entry, address, label)
        self._attr_unique_id = f"{DOMAIN}_{address}_fiat"

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
