"""Binary sensor platform for Air Alert Israel."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_CITY_ID, ATTR_CITY_NAME_HE, DOMAIN, INTEGRATION_NAME
from .models import CityConfig
from .runtime import TzevaAdomRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-city diagnostic binary sensors."""
    runtime: TzevaAdomRuntime = entry.runtime_data
    async_add_entities(
        AirAlertIsraelConnectionSensor(entry, runtime, city) for city in runtime.cities
    )


class AirAlertIsraelConnectionSensor(BinarySensorEntity):
    """Show whether the shared websocket connection is currently active."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "city_connection"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: TzevaAdomRuntime,
        city: CityConfig,
    ) -> None:
        self._entry = entry
        self._runtime = runtime
        self._city = city
        self._attr_unique_id = f"{entry.entry_id}_{city.id}_connection"

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._runtime.available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_CITY_ID: self._city.id,
            ATTR_CITY_NAME_HE: self._city.name_he,
            "connected_at": self._runtime.connected_at,
            "last_message_at": self._runtime.last_message_at,
            "reconnect_attempts": self._runtime.reconnect_attempts,
            "last_error": self._runtime.last_error,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"city_{self._city.id}")},
            name=self._city.name_he,
            manufacturer=INTEGRATION_NAME,
            model="Israel city monitor",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._runtime.async_add_listener(self.async_write_ha_state)
        )
