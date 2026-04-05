"""The Air Alert Israel integration."""

from __future__ import annotations

import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .city_catalog import async_refresh_city_catalog
from .const import CONF_CITIES, DOMAIN, INTEGRATION_NAME, PLATFORMS, SERVICE_REFRESH_CITY_CATALOG
from .runtime import TzevaAdomRuntime


def _build_entry_title(entry: ConfigEntry) -> str:
    city_count = len(entry.data.get(CONF_CITIES, []))
    return f"{INTEGRATION_NAME} ({city_count} cities)"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration and register shared services."""

    async def handle_refresh_city_catalog(call: ServiceCall) -> None:
        await async_refresh_city_catalog(hass)

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_CITY_CATALOG):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_CITY_CATALOG,
            handle_refresh_city_catalog,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Air Alert Israel from a config entry."""
    expected_title = _build_entry_title(entry)
    if entry.title != expected_title:
        hass.config_entries.async_update_entry(entry, title=expected_title)

    runtime = TzevaAdomRuntime(hass, entry)
    entry.runtime_data = runtime

    await runtime.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_prune_stale_entities(hass, entry, runtime.city_ids)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    runtime: TzevaAdomRuntime = entry.runtime_data

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await runtime.async_stop()

    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry after options updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_prune_stale_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    valid_city_ids: set[int],
) -> None:
    """Remove stale per-city entities after a reconfigure."""
    registry = er.async_get(hass)
    pattern = re.compile(rf"^{re.escape(entry.entry_id)}_(\d+)_(status|connection)$")
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity.unique_id or ""
        match = pattern.match(unique_id)
        if not match:
            continue
        if int(match.group(1)) not in valid_city_ids:
            registry.async_remove(entity.entity_id)
