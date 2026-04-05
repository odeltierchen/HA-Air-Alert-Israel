"""Diagnostics for Air Alert Israel."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .runtime import TzevaAdomRuntime


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict:
    """Return diagnostics for a config entry."""
    runtime: TzevaAdomRuntime = entry.runtime_data

    return {
        "entry_data": dict(entry.data),
        "entry_options": dict(entry.options),
        "runtime": {
            "available": runtime.available,
            "connected_at": runtime.connected_at,
            "last_message_at": runtime.last_message_at,
            "last_error": runtime.last_error,
            "reconnect_attempts": runtime.reconnect_attempts,
            "cities": {
                city.id: {
                    "name_he": city.name_he,
                    "state": asdict(runtime.get_city_state(city.id)),
                }
                for city in runtime.cities
            },
        },
    }
