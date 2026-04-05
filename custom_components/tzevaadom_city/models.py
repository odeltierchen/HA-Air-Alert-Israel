"""Dataclasses used by the TzevaAdom City integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class CityConfig:
    """A configured city."""

    id: int
    name_he: str


@dataclass(slots=True)
class CityState:
    """Runtime state for a city."""

    status: str
    last_event_type: str | None = None
    last_title_he: str | None = None
    last_body_he: str | None = None
    last_message_at: str | None = None
    last_changed_at: str | None = None
    cycle_started_at: str | None = None
    last_event_summary: str | None = None
    last_event_payload: dict[str, Any] = field(default_factory=dict)
    reset_token: int = 0
