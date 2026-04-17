"""Tests for the /api/therapists/search-by-address endpoint."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from therapist_finder.api.main import app
from therapist_finder.models import TherapistData
from therapist_finder.sources.geocode import GeocodingError, Location


def _fake_location() -> Location:
    return Location(
        lat=52.5396, lon=13.4127, display_name="Kastanienallee 12, 10435 Berlin"
    )


def test_search_by_address_success() -> None:
    """Happy path: geocoder + 1 source → ranked response."""
    near = TherapistData(
        name="Dr. Anna Beispiel",
        address="Kastanienallee 12, 10435 Berlin",
        email="anna@beispiel.de",
        telefon="030 1234567",
        lat=52.5396,
        lon=13.4127,
        sources=["osm"],
    )

    with (
        patch("therapist_finder.api.routes.therapists.Geocoder") as mock_geocoder_cls,
        patch("therapist_finder.api.routes.therapists._build_source") as mock_build,
    ):
        geocoder = mock_geocoder_cls.return_value
        geocoder.geocode.return_value = _fake_location()

        class _FakeSource:
            name = "osm"

            def search(self, params: object) -> list[TherapistData]:
                return [near]

            def close(self) -> None:
                return None

        mock_build.side_effect = lambda name, settings: (
            _FakeSource() if name == "osm" else None
        )

        client = TestClient(app)
        resp = client.post(
            "/api/therapists/search-by-address",
            json={
                "address": "Kastanienallee 12, 10435 Berlin",
                "max_results": 5,
                "sources": ["osm"],
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["with_email"] == 1
    assert body["origin_address"] == "Kastanienallee 12, 10435 Berlin"
    assert body["therapists"][0]["name"] == "Dr. Anna Beispiel"
    assert body["therapists"][0]["email"] == "anna@beispiel.de"
    assert body["therapists"][0]["sources"] == ["osm"]


def test_search_by_address_invalid_address() -> None:
    """Non-Berlin address → 400 with the geocoder's message."""
    with patch("therapist_finder.api.routes.therapists.Geocoder") as mock_geocoder_cls:
        mock_geocoder_cls.return_value.geocode.side_effect = GeocodingError(
            "outside Berlin"
        )
        client = TestClient(app)
        resp = client.post(
            "/api/therapists/search-by-address",
            json={"address": "Marienplatz, München", "sources": ["osm"]},
        )

    assert resp.status_code == 400
    assert "outside Berlin" in resp.json()["detail"]


def test_search_by_address_rejects_unknown_sources() -> None:
    """All sources unknown → 400 'No valid sources selected'."""
    with patch("therapist_finder.api.routes.therapists.Geocoder") as mock_geocoder_cls:
        mock_geocoder_cls.return_value.geocode.return_value = _fake_location()

        client = TestClient(app)
        resp = client.post(
            "/api/therapists/search-by-address",
            json={
                "address": "Kastanienallee 12, 10435 Berlin",
                "sources": ["does-not-exist"],
            },
        )

    assert resp.status_code == 400
    assert "No valid sources" in resp.json()["detail"]
