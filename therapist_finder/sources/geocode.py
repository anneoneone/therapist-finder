"""Geocoding helpers backed by Nominatim + Haversine distance."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from therapist_finder.sources.rate_limit import RateLimiter

BERLIN_LAT_RANGE = (52.3, 52.7)
BERLIN_LON_RANGE = (13.0, 13.8)


@dataclass(frozen=True)
class Location:
    """A geocoded location with coordinates and a human-readable label."""

    lat: float
    lon: float
    display_name: str


class GeocodingError(RuntimeError):
    """Raised when an address cannot be geocoded or falls outside Berlin."""


class Geocoder:
    """Thin wrapper around Nominatim with disk-cache + 1 rps rate limit."""

    def __init__(
        self,
        endpoint: str,
        user_agent: str,
        cache_dir: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Initialise the geocoder.

        Args:
            endpoint: Full Nominatim ``/search`` URL.
            user_agent: Identifying User-Agent required by Nominatim ToS.
            cache_dir: If given, JSON responses are cached there by address.
            client: Optional pre-built ``httpx.Client`` (useful in tests).
        """
        self._endpoint = endpoint
        self._cache_dir = cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=20.0,
        )
        self._owns_client = client is None
        self._rate_limiter = RateLimiter(min_delay_seconds=1.0)
        self._host = urlparse(endpoint).netloc

    def geocode(self, address: str, *, require_berlin: bool = True) -> Location:
        """Geocode ``address`` using Nominatim.

        Raises:
            GeocodingError: If no match is found or the result lies outside
                Berlin (when ``require_berlin`` is True).
        """
        key = address.strip().lower()
        cached = self._read_cache(key)
        if cached is None:
            self._rate_limiter.wait(self._host)
            resp = self._client.get(
                self._endpoint,
                params={
                    "q": address,
                    "format": "jsonv2",
                    "limit": 1,
                    "addressdetails": 1,
                    "countrycodes": "de",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            self._write_cache(key, payload)
        else:
            payload = cached

        if not payload:
            raise GeocodingError(f"No geocoding result for address: {address!r}")

        top: dict[str, Any] = payload[0]
        lat = float(top["lat"])
        lon = float(top["lon"])
        if require_berlin and not _is_in_berlin(lat, lon):
            raise GeocodingError(
                f"Address {address!r} geocoded outside Berlin (lat={lat}, lon={lon})"
            )
        return Location(
            lat=lat,
            lon=lon,
            display_name=top.get("display_name", address),
        )

    def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Geocoder:
        """Context manager entry."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Context manager exit closes the HTTP client."""
        self.close()

    def _cache_path(self, key: str) -> Path | None:
        if self._cache_dir is None:
            return None
        safe = "".join(c if c.isalnum() else "_" for c in key)[:120]
        return self._cache_dir / f"geocode_{safe}.json"

    def _read_cache(self, key: str) -> list[dict[str, Any]] | None:
        path = self._cache_path(key)
        if path is None or not path.exists():
            return None
        try:
            data: list[dict[str, Any]] = json.loads(path.read_text("utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, key: str, payload: list[dict[str, Any]]) -> None:
        path = self._cache_path(key)
        if path is None:
            return
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass


def geocode(address: str, *, endpoint: str, user_agent: str) -> Location:
    """Convenience one-shot geocode without caching (useful in tests/CLI)."""
    with Geocoder(endpoint=endpoint, user_agent=user_agent) as g:
        return g.geocode(address)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    r = 6371.0088
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _is_in_berlin(lat: float, lon: float) -> bool:
    return (
        BERLIN_LAT_RANGE[0] <= lat <= BERLIN_LAT_RANGE[1]
        and BERLIN_LON_RANGE[0] <= lon <= BERLIN_LON_RANGE[1]
    )
