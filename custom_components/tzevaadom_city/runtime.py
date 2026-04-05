"""Runtime websocket handling for Air Alert Israel."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError, ClientWebSocketResponse, WSMsgType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ALERT_IDLE_AFTER,
    CONF_ALL_CLEAR_IDLE_AFTER,
    CONF_CITIES,
    CONF_EARLY_WARNING_IDLE_AFTER,
    CONF_INCLUDE_NATIONWIDE,
    DEFAULT_ALERT_IDLE_AFTER,
    DEFAULT_ALL_CLEAR_IDLE_AFTER,
    DEFAULT_EARLY_WARNING_IDLE_AFTER,
    DEFAULT_INCLUDE_NATIONWIDE,
    DEFAULT_WS_URL,
    EARLY_WARNING_KEYWORDS_HE,
    EARLY_WARNING_TITLE_HE,
    EXIT_KEYWORDS_HE,
    EXIT_TITLE_HE,
    MIN_ALERT_IDLE_AFTER,
    MIN_ALL_CLEAR_IDLE_AFTER,
    MIN_EARLY_WARNING_IDLE_AFTER,
    NATIONWIDE_CITY_ID,
    NATIONWIDE_CITY_NAME,
    PRIMARY_THREAT_IDS,
    STATE_ALERT,
    STATE_ALL_CLEAR,
    STATE_EARLY_WARNING,
    STATE_IDLE,
)
from .models import CityConfig, CityState

_LOGGER = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class TzevaAdomRuntime:
    """Own the websocket connection and city states."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.session = async_get_clientsession(hass)

        city_objects = [
            CityConfig(id=int(city["id"]), name_he=str(city["name_he"]))
            for city in entry.data[CONF_CITIES]
        ]
        self.cities = tuple(sorted(city_objects, key=lambda city: city.name_he))
        self.city_ids = {city.id for city in self.cities}
        self.city_names = {city.name_he: city.id for city in self.cities}

        self.available = False
        self.connected_at: str | None = None
        self.last_message_at: str | None = None
        self.last_error: str | None = None
        self.reconnect_attempts = 0

        self.states: dict[int, CityState] = {
            city.id: CityState(status=STATE_IDLE) for city in self.cities
        }

        self._listeners: set[Callable[[], None]] = set()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._reset_tasks: dict[int, asyncio.Task] = {}
        self._websocket: ClientWebSocketResponse | None = None

    @property
    def ws_url(self) -> str:
        """Return the websocket URL."""
        return str(self.entry.data.get("ws_url", DEFAULT_WS_URL))

    @property
    def include_nationwide(self) -> bool:
        """Return whether nationwide messages should match all cities."""
        return bool(
            self.entry.options.get(
                CONF_INCLUDE_NATIONWIDE,
                self.entry.data.get(CONF_INCLUDE_NATIONWIDE, DEFAULT_INCLUDE_NATIONWIDE),
            )
        )

    @property
    def early_warning_idle_after(self) -> int:
        """Return early-warning fallback timeout."""
        value = int(
            self.entry.options.get(
                CONF_EARLY_WARNING_IDLE_AFTER,
                self.entry.data.get(
                    CONF_EARLY_WARNING_IDLE_AFTER,
                    DEFAULT_EARLY_WARNING_IDLE_AFTER,
                ),
            )
        )
        return max(value, MIN_EARLY_WARNING_IDLE_AFTER)

    @property
    def alert_idle_after(self) -> int:
        """Return alert fallback timeout."""
        value = int(
            self.entry.options.get(
                CONF_ALERT_IDLE_AFTER,
                self.entry.data.get(CONF_ALERT_IDLE_AFTER, DEFAULT_ALERT_IDLE_AFTER),
            )
        )
        return max(value, MIN_ALERT_IDLE_AFTER)

    @property
    def all_clear_idle_after(self) -> int:
        """Return all-clear display timeout."""
        value = int(
            self.entry.options.get(
                CONF_ALL_CLEAR_IDLE_AFTER,
                self.entry.data.get(
                    CONF_ALL_CLEAR_IDLE_AFTER,
                    DEFAULT_ALL_CLEAR_IDLE_AFTER,
                ),
            )
        )
        return max(value, MIN_ALL_CLEAR_IDLE_AFTER)

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a state listener."""
        self._listeners.add(listener)

        def _remove() -> None:
            self._listeners.discard(listener)

        return _remove

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def get_city_state(self, city_id: int) -> CityState:
        """Return the state for a configured city."""
        return self.states[city_id]

    async def async_start(self) -> None:
        """Start the websocket task."""
        self._stop_event.clear()
        self._task = self.entry.async_create_background_task(
            self.hass,
            self._run(),
            "air_alert_israel_websocket",
        )

    async def async_stop(self) -> None:
        """Stop the websocket task and any pending timeouts."""
        self._stop_event.set()

        for task in self._reset_tasks.values():
            task.cancel()
        self._reset_tasks.clear()

        if self._websocket is not None and not self._websocket.closed:
            await self._websocket.close()
        self._websocket = None

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        backoff = 5

        while not self._stop_event.is_set():
            try:
                await self._connect_and_listen()
                backoff = 5
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                _LOGGER.warning("Air Alert Israel websocket error: %s", exc)

            self.available = False
            self.connected_at = None
            self._notify()

            if self._stop_event.is_set():
                return

            self.reconnect_attempts += 1
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                return
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60)

    async def _connect_and_listen(self) -> None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0 Mobile Safari/537.36"
            ),
            "Origin": "https://www.tzevaadom.co.il",
            "Referer": "https://www.tzevaadom.co.il/en/",
            "tzofar": secrets.token_hex(16),
        }

        _LOGGER.info(
            "Connecting to Air Alert Israel websocket for %s configured cities",
            len(self.cities),
        )

        try:
            async with self.session.ws_connect(
                self.ws_url,
                headers=headers,
                heartbeat=60,
                autoping=True,
                autoclose=True,
                compress=0,
                timeout=30,
            ) as websocket:
                self._websocket = websocket
                self.available = True
                self.connected_at = _utcnow_iso()
                self.last_error = None
                self._notify()

                async for message in websocket:
                    if self._stop_event.is_set():
                        return

                    if message.type is WSMsgType.TEXT:
                        self.last_message_at = _utcnow_iso()
                        await self._handle_raw_message(message.data)
                        continue

                    if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
                        raise ConnectionError("Websocket closed")

                    if message.type is WSMsgType.ERROR:
                        raise ConnectionError("Websocket reported an error")
        finally:
            self._websocket = None

    async def _handle_raw_message(self, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            _LOGGER.debug("Ignoring non-JSON websocket message: %s", raw_message)
            return

        message_type = payload.get("type")
        data = payload.get("data")
        if not isinstance(data, dict):
            return

        if message_type == "ALERT":
            await self._handle_alert(data)
            return

        if message_type == "SYSTEM_MESSAGE":
            await self._handle_system_message(data)

    async def _handle_alert(self, data: dict[str, Any]) -> None:
        cities = data.get("cities")
        threat = data.get("threat")
        if not isinstance(cities, list) or threat not in PRIMARY_THREAT_IDS:
            return

        matched_city_ids: set[int] = set()

        if self.include_nationwide and NATIONWIDE_CITY_NAME in cities:
            matched_city_ids = set(self.city_ids)
        else:
            for city_name in cities:
                city_id = self.city_names.get(str(city_name))
                if city_id is not None:
                    matched_city_ids.add(city_id)

        if not matched_city_ids:
            return

        for city_id in matched_city_ids:
            await self._set_city_state(
                city_id=city_id,
                new_state=STATE_ALERT,
                event_type="ALERT",
                title_he=None,
                body_he=None,
                payload=data,
                summary="Primary alert",
            )

    async def _handle_system_message(self, data: dict[str, Any]) -> None:
        title_he = str(data.get("titleHe", "") or "")
        body_he = str(data.get("bodyHe", "") or "")
        cities_ids = data.get("citiesIds")
        if not isinstance(cities_ids, list):
            return

        matched_city_ids: set[int] = set()

        if self.include_nationwide and NATIONWIDE_CITY_ID in cities_ids:
            matched_city_ids = set(self.city_ids)
        else:
            for city_id in cities_ids:
                try:
                    normalized_city_id = int(city_id)
                except (TypeError, ValueError):
                    continue

                if normalized_city_id in self.city_ids:
                    matched_city_ids.add(normalized_city_id)

        if not matched_city_ids:
            return

        if self._is_early_warning(title_he, body_he):
            for city_id in matched_city_ids:
                await self._set_city_state(
                    city_id=city_id,
                    new_state=STATE_EARLY_WARNING,
                    event_type="SYSTEM_MESSAGE_EARLY_WARNING",
                    title_he=title_he,
                    body_he=body_he,
                    payload=data,
                    summary="Early warning",
                )
            return

        if self._is_all_clear(title_he, body_he):
            for city_id in matched_city_ids:
                await self._set_city_state(
                    city_id=city_id,
                    new_state=STATE_ALL_CLEAR,
                    event_type="SYSTEM_MESSAGE_ALL_CLEAR",
                    title_he=title_he,
                    body_he=body_he,
                    payload=data,
                    summary="All clear",
                )

    def _is_early_warning(self, title_he: str, body_he: str) -> bool:
        return EARLY_WARNING_TITLE_HE in title_he and any(
            keyword in body_he for keyword in EARLY_WARNING_KEYWORDS_HE
        )

    def _is_all_clear(self, title_he: str, body_he: str) -> bool:
        return EXIT_TITLE_HE in title_he and any(
            keyword in body_he for keyword in EXIT_KEYWORDS_HE
        )

    async def _set_city_state(
        self,
        *,
        city_id: int,
        new_state: str,
        event_type: str,
        title_he: str | None,
        body_he: str | None,
        payload: dict[str, Any],
        summary: str,
    ) -> None:
        state = self.states[city_id]

        if new_state == STATE_EARLY_WARNING and state.status == STATE_ALERT:
            return

        now = _utcnow_iso()
        if new_state in (STATE_EARLY_WARNING, STATE_ALERT):
            cycle_started_at = state.cycle_started_at or now
        else:
            cycle_started_at = None

        state.status = new_state
        state.last_event_type = event_type
        state.last_title_he = title_he
        state.last_body_he = body_he
        state.last_message_at = now
        state.last_changed_at = now
        state.cycle_started_at = cycle_started_at
        state.last_event_summary = summary
        state.last_event_payload = payload
        state.reset_token += 1

        self._schedule_reset(city_id, new_state, state.reset_token)
        self._notify()

    def _schedule_reset(self, city_id: int, state: str, token: int) -> None:
        existing = self._reset_tasks.pop(city_id, None)
        if existing is not None:
            existing.cancel()

        if state != STATE_ALL_CLEAR:
            return

        delay = self.all_clear_idle_after

        self._reset_tasks[city_id] = self.hass.async_create_task(
            self._async_reset_later(city_id, state, token, delay)
        )

    async def _async_reset_later(
        self,
        city_id: int,
        expected_state: str,
        token: int,
        delay: int,
    ) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        state = self.states[city_id]
        if state.reset_token != token or state.status != expected_state:
            return

        now = _utcnow_iso()
        state.status = STATE_IDLE
        state.last_changed_at = now
        state.last_event_summary = f"{state.last_event_summary or expected_state} timed out"
        state.cycle_started_at = None
        state.reset_token += 1
        self._reset_tasks.pop(city_id, None)
        self._notify()
