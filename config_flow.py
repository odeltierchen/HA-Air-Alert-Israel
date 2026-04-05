"""Config flow for Air Alert Israel."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .city_catalog import CityCatalogError, async_load_city_catalog, search_city_catalog
from .const import (
    CONF_ALERT_IDLE_AFTER,
    CONF_ALL_CLEAR_IDLE_AFTER,
    CONF_CITIES,
    CONF_CITY_SEARCH,
    CONF_EARLY_WARNING_IDLE_AFTER,
    CONF_INCLUDE_NATIONWIDE,
    CONF_KEEP_CITIES,
    CONF_PICKED_CITIES,
    CONF_SEARCH_MORE,
    DEFAULT_ALERT_IDLE_AFTER,
    DEFAULT_ALL_CLEAR_IDLE_AFTER,
    DEFAULT_EARLY_WARNING_IDLE_AFTER,
    DEFAULT_INCLUDE_NATIONWIDE,
    DOMAIN,
    INTEGRATION_NAME,
    MIN_ALERT_IDLE_AFTER,
    MIN_ALL_CLEAR_IDLE_AFTER,
    MIN_EARLY_WARNING_IDLE_AFTER,
)

_SINGLETON_UNIQUE_ID = DOMAIN


def _city_label(city_name_he: str, city_id: int) -> str:
    return f"{city_name_he} (ID {city_id})"


def _entry_title(cities: Mapping[int, str]) -> str:
    return f"{INTEGRATION_NAME} ({len(cities)} cities)"


class AirAlertIsraelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Air Alert Israel."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        self._city_catalog: dict[str, dict] = {}
        self._search_matches: list[tuple[str, int]] = []
        self._selected_cities: dict[int, str] = {}
        self._search_query = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial search step."""
        if self.source == config_entries.SOURCE_USER:
            await self.async_set_unique_id(_SINGLETON_UNIQUE_ID)
            self._abort_if_unique_id_configured()

        return await self._async_search_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()
        current_cities = entry.data[CONF_CITIES]

        if not self._selected_cities:
            self._selected_cities = {
                int(city["id"]): str(city["name_he"]) for city in current_cities
            }

        errors: dict[str, str] = {}
        if user_input is not None:
            kept = {
                int(value.split("|", 1)[1]): value.split("|", 1)[0]
                for value in user_input.get(CONF_KEEP_CITIES, [])
            }
            self._selected_cities = kept

            if not kept and not user_input.get(CONF_SEARCH_MORE, False):
                errors["base"] = "at_least_one_city"
            elif user_input.get(CONF_SEARCH_MORE, False):
                return await self.async_step_user()
            else:
                return await self._async_finish_reconfigure(entry)

        options = [
            selector.SelectOptionDict(
                value=f"{city['name_he']}|{city['id']}",
                label=_city_label(str(city["name_he"]), int(city["id"])),
            )
            for city in current_cities
        ]
        defaults = [option["value"] for option in options]

        schema = vol.Schema(
            {
                vol.Required(CONF_KEEP_CITIES, default=defaults): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_SEARCH_MORE, default=False): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "selected": ", ".join(city["name_he"] for city in current_cities) or "—"
            },
        )

    async def async_step_pick_cities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick one or more cities from the current search matches."""
        errors: dict[str, str] = {}
        if user_input is not None:
            picked_values: list[str] = user_input.get(CONF_PICKED_CITIES, [])
            if not picked_values:
                errors["base"] = "pick_one_city"
            else:
                for picked in picked_values:
                    city_name_he, city_id_text = picked.split("|", 1)
                    self._selected_cities[int(city_id_text)] = city_name_he

                if user_input.get(CONF_SEARCH_MORE, False):
                    return await self.async_step_user()

                if self.source == config_entries.SOURCE_RECONFIGURE:
                    return await self._async_finish_reconfigure(
                        self._get_reconfigure_entry()
                    )

                return self.async_create_entry(
                    title=_entry_title(self._selected_cities),
                    data=self._build_entry_data(),
                )

        options = [
            selector.SelectOptionDict(
                value=f"{city_name_he}|{city_id}",
                label=_city_label(city_name_he, city_id),
            )
            for city_name_he, city_id in self._search_matches
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_PICKED_CITIES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_SEARCH_MORE, default=False): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="pick_cities",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "query": self._search_query,
                "selected": ", ".join(self._selected_cities.values()) or "—",
            },
        )

    async def _async_search_step(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._search_query = user_input[CONF_CITY_SEARCH]
            try:
                self._city_catalog = await async_load_city_catalog(self.hass)
            except CityCatalogError:
                errors["base"] = "cannot_load_city_catalog"
            else:
                self._search_matches = search_city_catalog(
                    self._city_catalog,
                    self._search_query,
                )
                if not self._search_matches:
                    errors["base"] = "no_city_matches"
                else:
                    return await self.async_step_pick_cities()

        schema = vol.Schema(
            {
                vol.Required(CONF_CITY_SEARCH): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "selected": ", ".join(self._selected_cities.values()) or "—",
            },
        )

    async def _async_finish_reconfigure(self, entry) -> FlowResult:
        await self.async_set_unique_id(_SINGLETON_UNIQUE_ID)
        self._abort_if_unique_id_mismatch()

        self.hass.config_entries.async_update_entry(
            entry,
            title=_entry_title(self._selected_cities),
        )
        return self.async_update_reload_and_abort(
            entry,
            data_updates={
                CONF_CITIES: [
                    {"id": city_id, "name_he": city_name_he}
                    for city_id, city_name_he in sorted(
                        self._selected_cities.items(),
                        key=lambda item: item[1],
                    )
                ]
            },
        )

    def _build_entry_data(self) -> dict[str, Any]:
        return {
            CONF_NAME: INTEGRATION_NAME,
            CONF_CITIES: [
                {"id": city_id, "name_he": city_name_he}
                for city_id, city_name_he in sorted(
                    self._selected_cities.items(),
                    key=lambda item: item[1],
                )
            ],
            CONF_INCLUDE_NATIONWIDE: DEFAULT_INCLUDE_NATIONWIDE,
            CONF_EARLY_WARNING_IDLE_AFTER: DEFAULT_EARLY_WARNING_IDLE_AFTER,
            CONF_ALERT_IDLE_AFTER: DEFAULT_ALERT_IDLE_AFTER,
            CONF_ALL_CLEAR_IDLE_AFTER: DEFAULT_ALL_CLEAR_IDLE_AFTER,
        }

    @staticmethod
    def async_get_options_flow(config_entry):
        return AirAlertIsraelOptionsFlow(config_entry)


class AirAlertIsraelOptionsFlow(config_entries.OptionsFlow):
    """Handle Air Alert Israel options."""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            user_input[CONF_EARLY_WARNING_IDLE_AFTER] = max(
                int(user_input[CONF_EARLY_WARNING_IDLE_AFTER]),
                MIN_EARLY_WARNING_IDLE_AFTER,
            )
            user_input[CONF_ALERT_IDLE_AFTER] = max(
                int(user_input[CONF_ALERT_IDLE_AFTER]),
                MIN_ALERT_IDLE_AFTER,
            )
            user_input[CONF_ALL_CLEAR_IDLE_AFTER] = max(
                int(user_input[CONF_ALL_CLEAR_IDLE_AFTER]),
                MIN_ALL_CLEAR_IDLE_AFTER,
            )
            return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_INCLUDE_NATIONWIDE,
                    default=self.config_entry.options.get(
                        CONF_INCLUDE_NATIONWIDE,
                        self.config_entry.data.get(
                            CONF_INCLUDE_NATIONWIDE,
                            DEFAULT_INCLUDE_NATIONWIDE,
                        ),
                    ),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_EARLY_WARNING_IDLE_AFTER,
                    default=self.config_entry.options.get(
                        CONF_EARLY_WARNING_IDLE_AFTER,
                        self.config_entry.data.get(
                            CONF_EARLY_WARNING_IDLE_AFTER,
                            DEFAULT_EARLY_WARNING_IDLE_AFTER,
                        ),
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_EARLY_WARNING_IDLE_AFTER,
                        max=7200,
                        step=30,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    CONF_ALERT_IDLE_AFTER,
                    default=self.config_entry.options.get(
                        CONF_ALERT_IDLE_AFTER,
                        self.config_entry.data.get(
                            CONF_ALERT_IDLE_AFTER,
                            DEFAULT_ALERT_IDLE_AFTER,
                        ),
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_ALERT_IDLE_AFTER,
                        max=7200,
                        step=30,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    CONF_ALL_CLEAR_IDLE_AFTER,
                    default=self.config_entry.options.get(
                        CONF_ALL_CLEAR_IDLE_AFTER,
                        self.config_entry.data.get(
                            CONF_ALL_CLEAR_IDLE_AFTER,
                            DEFAULT_ALL_CLEAR_IDLE_AFTER,
                        ),
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_ALL_CLEAR_IDLE_AFTER,
                        max=1800,
                        step=10,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
