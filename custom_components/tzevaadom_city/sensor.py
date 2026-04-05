"""Sensor platform for Air Alert Israel."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up city state sensors."""
    runtime: TzevaAdomRuntime = entry.runtime_data
    async_add_entities(
        AirAlertIsraelCityStatusSensor(entry, runtime, city) for city in runtime.cities
    )


class AirAlertIsraelCityStatusSensor(SensorEntity):
    """Represent the state of one monitored city."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "city_status"
    _attr_icon = "mdi:shield-alert"

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: TzevaAdomRuntime,
        city: CityConfig,
    ) -> None:
        self._entry = entry
        self._runtime = runtime
        self._city = city
        self._attr_unique_id = f"{entry.entry_id}_{city.id}_status"

    @property
    def available(self) -> bool:
        return self._runtime.available

    @property
    def native_value(self) -> str:
        return self._runtime.get_city_state(self._city.id).status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        city_state = self._runtime.get_city_state(self._city.id)
        return {
            ATTR_CITY_ID: self._city.id,
            ATTR_CITY_NAME_HE: self._city.name_he,
            "last_event_type": city_state.last_event_type,
            "last_title_he": city_state.last_title_he,
            "last_body_he": city_state.last_body_he,
            "last_message_at": city_state.last_message_at,
            "last_changed_at": city_state.last_changed_at,
            "cycle_started_at": city_state.cycle_started_at,
            "last_event_summary": city_state.last_event_summary,
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
