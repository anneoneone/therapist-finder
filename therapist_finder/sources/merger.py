"""Merge, deduplicate, and rank healthcare-provider results across sources."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
import unicodedata

from therapist_finder.models import TherapistData
from therapist_finder.sources.geocode import Geocoder, GeocodingError, haversine_km

logger = logging.getLogger(__name__)

_TITLE_RE = re.compile(
    r"\b(dr\.?(\s*med\.?)?|prof\.?|dipl\.?-?psych\.?|m\.sc\.?|b\.sc\.?)\b",
    re.IGNORECASE,
)
_HOUSENUMBER_RE = re.compile(r"\b(\d{1,4}[a-z]?)\b", re.IGNORECASE)
_POSTCODE_RE = re.compile(r"\b(\d{5})\b")


@dataclass(frozen=True)
class _Origin:
    lat: float
    lon: float


def merge_and_rank(
    results: dict[str, list[TherapistData]],
    origin_lat: float,
    origin_lon: float,
    limit: int,
    *,
    geocoder: Geocoder | None = None,
) -> list[TherapistData]:
    """Merge per-source results, dedupe, rank by distance, and truncate.

    Args:
        results: Mapping of source name → list of providers from that source.
        origin_lat: Latitude of the search origin (geocoded user address).
        origin_lon: Longitude of the search origin.
        limit: Return at most this many providers (sorted by distance asc).
        geocoder: Optional :class:`Geocoder` used to resolve lat/lon for
            providers that don't come with coordinates (e.g. 116117 / PTK).

    Returns:
        Deduplicated providers with ``distance_km`` populated where possible,
        sorted by ascending distance. Providers whose distance cannot be
        determined are placed at the end.
    """
    buckets: dict[tuple[str, str], TherapistData] = {}
    fallback_key_counter = 0
    for source_name, entries in results.items():
        for entry in entries:
            key = _dedup_key(entry)
            if key is None:
                fallback_key_counter += 1
                key = ("_unique_", f"{source_name}:{fallback_key_counter}")
            if key in buckets:
                buckets[key] = _merge_one(buckets[key], entry)
            else:
                # Ensure the source is recorded even if the producer forgot
                if source_name not in entry.sources:
                    entry = entry.model_copy(
                        update={"sources": [*entry.sources, source_name]}
                    )
                buckets[key] = entry

    merged = list(buckets.values())

    for i, provider in enumerate(merged):
        if (provider.lat is None or provider.lon is None) and geocoder is not None:
            coords = _try_geocode(provider, geocoder)
            if coords is not None:
                merged[i] = provider.model_copy(
                    update={"lat": coords[0], "lon": coords[1]}
                )

    ranked = [_with_distance(p, origin_lat, origin_lon) for p in merged]
    ranked.sort(key=lambda p: (p.distance_km is None, p.distance_km or 0.0))
    return ranked[:limit]


def _dedup_key(entry: TherapistData) -> tuple[str, str] | None:
    normalised_name = _normalise_name(entry.name)
    postcode = _extract_postcode(entry.address or "")
    number = _extract_housenumber(entry.address or "")
    if normalised_name and (postcode or number):
        return ("name_addr", f"{normalised_name}|{postcode}|{number}")
    if entry.email:
        return ("email", entry.email.strip().lower())
    if normalised_name:
        return ("name", normalised_name)
    return None


def _merge_one(existing: TherapistData, new: TherapistData) -> TherapistData:
    def _pick(a: str | None, b: str | None) -> str | None:
        if a and b:
            return a if len(a) >= len(b) else b
        return a or b

    def _merge_list(a: list[str], b: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for item in [*a, *b]:
            if item and item not in seen:
                seen.add(item)
                merged.append(item)
        return merged

    merged_sources = _merge_list(existing.sources, new.sources)
    return existing.model_copy(
        update={
            "name": _pick(existing.name, new.name) or existing.name,
            "address": _pick(existing.address, new.address),
            "telefon": _pick(existing.telefon, new.telefon),
            "email": _pick(existing.email, new.email),
            "website": _pick(existing.website, new.website),
            "therapieform": _merge_list(existing.therapieform, new.therapieform),
            "sprechzeiten": _merge_list(existing.sprechzeiten, new.sprechzeiten),
            "languages": _merge_list(existing.languages, new.languages),
            "insurance_type": existing.insurance_type or new.insurance_type,
            "specialty": existing.specialty or new.specialty,
            "lat": existing.lat if existing.lat is not None else new.lat,
            "lon": existing.lon if existing.lon is not None else new.lon,
            "sources": merged_sources,
        }
    )


def _with_distance(
    provider: TherapistData, origin_lat: float, origin_lon: float
) -> TherapistData:
    if provider.lat is None or provider.lon is None:
        return provider
    distance = haversine_km(origin_lat, origin_lon, provider.lat, provider.lon)
    return provider.model_copy(update={"distance_km": round(distance, 3)})


def _try_geocode(
    provider: TherapistData, geocoder: Geocoder
) -> tuple[float, float] | None:
    if not provider.address:
        return None
    query = provider.address
    if "berlin" not in query.lower():
        query = f"{query}, Berlin"
    try:
        loc = geocoder.geocode(query, require_berlin=False)
    except (GeocodingError, Exception) as e:  # noqa: BLE001
        logger.debug("Geocoding failed for %s: %s", query, e)
        return None
    return loc.lat, loc.lon


def _normalise_name(name: str) -> str:
    if not name:
        return ""
    cleaned = _TITLE_RE.sub("", name)
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(c for c in cleaned if not unicodedata.combining(c))
    cleaned = re.sub(r"[^a-zA-Z\s-]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    parts = [p for p in cleaned.split(" ") if p]
    return parts[-1] if parts else ""


def _extract_postcode(address: str) -> str:
    m = _POSTCODE_RE.search(address)
    return m.group(1) if m else ""


def _extract_housenumber(address: str) -> str:
    m = _HOUSENUMBER_RE.search(address)
    return m.group(1) if m else ""
