"""Geocoding helpers (Photon by default, Nominatim supported) + haversine."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from therapist_finder.sources.rate_limit import RateLimiter

BERLIN_LAT_RANGE = (52.3, 52.7)
BERLIN_LON_RANGE = (13.0, 13.8)

Provider = Literal["photon", "nominatim"]


@dataclass(frozen=True)
class Location:
    """A geocoded location with coordinates and a human-readable label."""

    lat: float
    lon: float
    display_name: str


class GeocodingError(RuntimeError):
    """Raised when an address cannot be geocoded or falls outside Berlin."""


def _detect_provider(endpoint: str) -> Provider:
    return "photon" if "photon" in endpoint.lower() else "nominatim"


class Geocoder:
    """Geocoder supporting Photon (default) and Nominatim.

    Provider is detected by the endpoint URL: a ``photon`` host selects
    Photon's GeoJSON response shape, anything else is treated as Nominatim.
    Both providers use OSM data; Photon (komoot.io) has much laxer
    per-IP rate limits and is the safer default for shared cloud IPs.
    """

    def __init__(
        self,
        endpoint: str,
        user_agent: str,
        cache_dir: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Initialise the geocoder.

        Args:
            endpoint: Full geocoder URL (Photon ``/api/`` or Nominatim ``/search``).
            user_agent: Identifying User-Agent.
            cache_dir: If given, JSON responses are cached there by address.
            client: Optional pre-built ``httpx.Client`` (useful in tests).
        """
        self._endpoint = endpoint
        self._provider: Provider = _detect_provider(endpoint)
        self._cache_dir = cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=20.0,
        )
        self._owns_client = client is None
        # Photon publishes no hard rate limit; stay polite with a small delay.
        # Nominatim requires ≤1 rps.
        min_delay = 0.2 if self._provider == "photon" else 1.0
        self._rate_limiter = RateLimiter(min_delay_seconds=min_delay)
        self._host = urlparse(endpoint).netloc

    def geocode(self, address: str, *, require_berlin: bool = True) -> Location:
        """Geocode ``address`` using the configured provider.

        Raises:
            GeocodingError: If no match is found or the result lies outside
                Berlin (when ``require_berlin`` is True).
        """
        key = f"{self._provider}:{address.strip().lower()}"
        cached = self._read_cache(key)
        if cached is None:
            self._rate_limiter.wait(self._host)
            resp = self._client.get(self._endpoint, params=self._params(address))
            resp.raise_for_status()
            payload = resp.json()
            self._write_cache(key, payload)
        else:
            payload = cached

        lat, lon, display_name = self._parse(payload, address)
        if require_berlin and not _is_in_berlin(lat, lon):
            raise GeocodingError(
                f"Address {address!r} geocoded outside Berlin (lat={lat}, lon={lon})"
            )
        return Location(lat=lat, lon=lon, display_name=display_name)

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

    def _params(self, address: str) -> dict[str, Any]:
        if self._provider == "photon":
            return {"q": address, "limit": 1, "lang": "de"}
        return {
            "q": address,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            "countrycodes": "de",
        }

    def _parse(self, payload: Any, address: str) -> tuple[float, float, str]:
        if self._provider == "photon":
            features = (payload or {}).get("features") or []
            if not features:
                raise GeocodingError(f"No geocoding result for address: {address!r}")
            top = features[0]
            coords = top.get("geometry", {}).get("coordinates") or []
            if len(coords) < 2:
                raise GeocodingError(f"Malformed Photon response for {address!r}")
            lon, lat = float(coords[0]), float(coords[1])
            display_name = _photon_display_name(top.get("properties", {})) or address
            return lat, lon, display_name

        # Nominatim
        if not payload:
            raise GeocodingError(f"No geocoding result for address: {address!r}")
        top = payload[0]
        lat = float(top["lat"])
        lon = float(top["lon"])
        return lat, lon, top.get("display_name", address)

    def _cache_path(self, key: str) -> Path | None:
        if self._cache_dir is None:
            return None
        safe = "".join(c if c.isalnum() else "_" for c in key)[:120]
        return self._cache_dir / f"geocode_{safe}.json"

    def _read_cache(self, key: str) -> Any | None:
        path = self._cache_path(key)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, key: str, payload: Any) -> None:
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


def _photon_display_name(props: dict[str, Any]) -> str:
    parts = [
        props.get("street"),
        props.get("housenumber"),
        props.get("postcode"),
        props.get("city") or props.get("name"),
    ]
    flat = " ".join(str(p) for p in parts if p)
    return flat.strip()


def _is_in_berlin(lat: float, lon: float) -> bool:
    return (
        BERLIN_LAT_RANGE[0] <= lat <= BERLIN_LAT_RANGE[1]
        and BERLIN_LON_RANGE[0] <= lon <= BERLIN_LON_RANGE[1]
    )
