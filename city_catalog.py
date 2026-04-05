"""City catalog helpers."""

from __future__ import annotations

import logging
import re
import unicodedata
from difflib import SequenceMatcher

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import CATALOG_STORE_KEY, CATALOG_STORE_VERSION, CITY_CATALOG_URL

_LOGGER = logging.getLogger(__name__)

_HEBREW_START = 0x0590
_HEBREW_END = 0x05FF

# Curated aliases for common Latin spellings that are often searched from abroad.
_CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "הוד השרון": (
        "hod hasharon",
        "hod ha sharon",
        "hod-ha-sharon",
        "hodhasharon",
    ),
    "רמת השרון": (
        "ramat hasharon",
        "ramat ha sharon",
        "ramat-ha-sharon",
        "ramath hasharon",
    ),
    "תל אביב - יפו": (
        "tel aviv",
        "tel aviv yafo",
        "tel aviv jaffa",
        "tel-aviv",
        "tel aviv-yafo",
        "tel aviv yaffa",
    ),
    "ירושלים": ("jerusalem", "yerushalayim"),
    "חיפה": ("haifa",),
    "באר שבע": ("beer sheva", "be'er sheva", "beersheba"),
    "כפר סבא": ("kfar saba", "kefar saba"),
    "רעננה": ("raanana", "ra'anana"),
    "הרצליה": ("herzliya", "herzlia"),
    "פתח תקווה": ("petah tikva", "petach tikva", "petah tiqwa"),
}


class CityCatalogError(Exception):
    """Raised when the city catalog cannot be loaded."""


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    cleaned: list[str] = []
    for char in normalized:
        if unicodedata.combining(char):
            continue
        if char.isalnum() or _HEBREW_START <= ord(char) <= _HEBREW_END:
            cleaned.append(char)
        else:
            cleaned.append(" ")
    return " ".join("".join(cleaned).split())


def _compact(value: str) -> str:
    return value.replace(" ", "")


def _is_latinish(value: str) -> bool:
    return any("a" <= char <= "z" for char in value)


def _strip_ha_tokens(value: str) -> str:
    tokens = value.split()
    stripped: list[str] = []
    for index, token in enumerate(tokens):
        if token == "ha":
            continue
        if index > 0 and token.startswith("ha") and len(token) > 3:
            stripped.append(token[2:])
        else:
            stripped.append(token)
    return " ".join(stripped)


def _latin_skeleton(value: str) -> str:
    skeleton = re.sub(r"[aeiouy]", "", _compact(value))
    return skeleton or _compact(value)


def _term_variants(value: str) -> set[str]:
    normalized = _normalize(value)
    if not normalized:
        return set()

    variants = {
        normalized,
        _compact(normalized),
    }

    if _is_latinish(normalized):
        stripped = _strip_ha_tokens(normalized)
        variants.add(stripped)
        variants.add(_compact(stripped))
        variants.add(_latin_skeleton(normalized))
        variants.add(_latin_skeleton(stripped))

    return {variant for variant in variants if variant}


def _coerce_catalog(raw: object) -> dict[str, dict]:
    if not isinstance(raw, dict):
        raise CityCatalogError("City catalog root is not a mapping")

    cities = raw.get("cities")
    if not isinstance(cities, dict):
        raise CityCatalogError("City catalog is missing the 'cities' mapping")

    cleaned: dict[str, dict] = {}
    for city_name_he, meta in cities.items():
        if not isinstance(city_name_he, str) or not isinstance(meta, dict):
            continue

        city_id = meta.get("id")
        try:
            city_id = int(city_id)
        except (TypeError, ValueError):
            continue

        cleaned[city_name_he] = {
            "id": city_id,
            "name": str(meta.get("name", "")),
            "nameHe": str(meta.get("nameHe", "")),
            "nameEn": str(meta.get("nameEn", "")),
            "label": str(meta.get("label", "")),
            "value": str(meta.get("value", "")),
        }

    if not cleaned:
        raise CityCatalogError("City catalog is empty")

    return cleaned


async def async_load_city_catalog(
    hass: HomeAssistant,
    *,
    force_refresh: bool = False,
) -> dict[str, dict]:
    """Load the city catalog from cache or refresh it from the network."""
    store: Store[dict] = Store(hass, CATALOG_STORE_VERSION, CATALOG_STORE_KEY)
    cached = None if force_refresh else await store.async_load()

    if cached is not None:
        try:
            return _coerce_catalog(cached)
        except CityCatalogError:
            _LOGGER.warning("Ignoring invalid cached city catalog")

    catalog = await async_refresh_city_catalog(hass)
    if catalog:
        return catalog

    raise CityCatalogError("Unable to load the city catalog")


async def async_refresh_city_catalog(hass: HomeAssistant) -> dict[str, dict]:
    """Refresh the city catalog from the network and update the cache."""
    session = async_get_clientsession(hass)
    store: Store[dict] = Store(hass, CATALOG_STORE_VERSION, CATALOG_STORE_KEY)

    try:
        async with async_timeout.timeout(20):
            async with session.get(CITY_CATALOG_URL) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
    except Exception as exc:
        _LOGGER.error("Cannot refresh city catalog: %s", exc)
        cached = await store.async_load()
        if cached is not None:
            return _coerce_catalog(cached)
        raise CityCatalogError("Unable to refresh the city catalog") from exc

    catalog = _coerce_catalog(payload)
    await store.async_save({"cities": catalog})
    return catalog


def _city_search_terms(city_name_he: str, meta: dict) -> set[str]:
    raw_terms: set[str] = {
        city_name_he,
        str(meta.get("nameHe", "")),
        str(meta.get("nameEn", "")),
        str(meta.get("name", "")),
        str(meta.get("label", "")),
        str(meta.get("value", "")),
    }
    raw_terms.update(_CITY_ALIASES.get(city_name_he, ()))

    terms: set[str] = set()
    for raw in raw_terms:
        if not raw:
            continue
        terms.update(_term_variants(raw))
    return terms


def search_city_catalog(
    catalog: dict[str, dict],
    query: str,
    *,
    limit: int = 50,
) -> list[tuple[str, int]]:
    """Search the city catalog by Hebrew names, English names, or Latin spellings."""
    normalized_query = _normalize(query)
    if not normalized_query:
        return []

    query_variants = _term_variants(normalized_query)
    latin_query = _is_latinish(normalized_query)
    direct_matches: list[tuple[int, int, str, int]] = []
    fuzzy_matches: list[tuple[float, int, str, int]] = []

    for city_name_he, meta in catalog.items():
        city_id = meta["id"]
        terms = _city_search_terms(city_name_he, meta)
        if not terms:
            continue

        best_rank: int | None = None
        for query_term in query_variants:
            for term in terms:
                if query_term == term:
                    best_rank = 0 if best_rank is None else min(best_rank, 0)
                elif term.startswith(query_term):
                    best_rank = 1 if best_rank is None else min(best_rank, 1)
                elif query_term in term:
                    best_rank = 2 if best_rank is None else min(best_rank, 2)

        if best_rank is not None:
            direct_matches.append((best_rank, len(city_name_he), city_name_he, city_id))
            continue

        if not latin_query:
            continue

        query_keys = {_compact(variant) for variant in query_variants}
        similarities = [
            SequenceMatcher(None, query_key, _compact(term)).ratio()
            for query_key in query_keys
            for term in terms
            if _is_latinish(term)
        ]
        if not similarities:
            continue

        best_similarity = max(similarities)
        if best_similarity >= 0.74:
            fuzzy_matches.append((best_similarity, len(city_name_he), city_name_he, city_id))

    if direct_matches:
        direct_matches.sort(key=lambda item: (item[0], item[1], item[2]))
        return [(city_name_he, city_id) for _, _, city_name_he, city_id in direct_matches[:limit]]

    fuzzy_matches.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [(city_name_he, city_id) for _, _, city_name_he, city_id in fuzzy_matches[:limit]]
