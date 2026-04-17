"""OpenStreetMap Overpass API source for healthcare providers."""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx

from therapist_finder.models import TherapistData
from therapist_finder.sources.base import SearchParams, TherapistSource

logger = logging.getLogger(__name__)

_SPECIALTY_KEYWORDS = {
    "psychotherapeut": ("psychotherapist",),
    "psychiater": ("psychiatrist",),
    "arzt": ("doctor",),
}


class OverpassSource(TherapistSource):
    """Query Overpass API for healthcare nodes around a location."""

    name = "osm"

    def __init__(
        self,
        endpoint: str,
        user_agent: str,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
    ) -> None:
        """Initialise the Overpass source.

        Args:
            endpoint: Full Overpass ``/api/interpreter`` URL.
            user_agent: Identifying User-Agent.
            client: Optional pre-built ``httpx.Client`` (useful in tests).
            timeout: HTTP timeout in seconds.
        """
        self._endpoint = endpoint
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=timeout,
        )
        self._owns_client = client is None

    def search(self, params: SearchParams) -> list[TherapistData]:
        """Return healthcare nodes within ``radius_km`` of the search origin."""
        query = self._build_query(params)
        resp = self._client.post(self._endpoint, data={"data": query})
        resp.raise_for_status()
        payload = resp.json()
        elements = payload.get("elements", [])
        results: list[TherapistData] = []
        for el in elements:
            therapist = self._element_to_therapist(el)
            if therapist is not None:
                results.append(therapist)
        logger.info("OSM Overpass returned %d providers", len(results))
        return results

    def close(self) -> None:
        """Close the HTTP client if owned by this instance."""
        if self._owns_client:
            self._client.close()

    def _build_query(self, params: SearchParams) -> str:
        keywords = _keywords_for(params.specialty)
        # Match psychotherapist, doctor, etc. via both ``healthcare`` and
        # ``amenity`` tags; use a regex alternation to keep the query short.
        regex = "|".join(keywords)
        radius_m = int(params.radius_km * 1000)
        return (
            "[out:json][timeout:45];"
            "("
            f'nwr["healthcare"~"{regex}"]'
            f"(around:{radius_m},{params.lat},{params.lon});"
            f'nwr["amenity"="doctors"]'
            f"(around:{radius_m},{params.lat},{params.lon});"
            ");"
            "out center tags;"
        )

    def _element_to_therapist(
        self, element: dict[str, Any]
    ) -> TherapistData | None:
        tags = cast(dict[str, str], element.get("tags") or {})
        name = tags.get("name") or tags.get("operator")
        if not name:
            return None

        address = _format_address(tags)
        lat, lon = _element_coords(element)
        languages = _split_csv(tags.get("language") or tags.get("language:de", ""))
        specialty_tag = (
            tags.get("healthcare:speciality")
            or tags.get("healthcare")
            or tags.get("amenity")
        )

        return TherapistData(
            name=name,
            address=address,
            telefon=tags.get("phone") or tags.get("contact:phone"),
            email=tags.get("email") or tags.get("contact:email"),
            website=tags.get("website") or tags.get("contact:website"),
            therapieform=[specialty_tag] if specialty_tag else [],
            languages=languages,
            lat=lat,
            lon=lon,
            sources=[self.name],
        )


def _keywords_for(specialty: str) -> tuple[str, ...]:
    key = (specialty or "").strip().lower()
    for label, keywords in _SPECIALTY_KEYWORDS.items():
        if label in key:
            return keywords
    # Default: cover therapists and doctors both
    return ("psychotherapist", "doctor", "psychiatrist")


def _element_coords(element: dict[str, Any]) -> tuple[float | None, float | None]:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center") or {}
    if "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None, None


def _format_address(tags: dict[str, str]) -> str | None:
    street = tags.get("addr:street")
    housenumber = tags.get("addr:housenumber")
    postcode = tags.get("addr:postcode")
    city = tags.get("addr:city")
    line1 = " ".join(x for x in (street, housenumber) if x)
    line2 = " ".join(x for x in (postcode, city) if x)
    joined = ", ".join(x for x in (line1, line2) if x)
    return joined or None


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()] if value else []
