"""Tests for healthcare-provider data sources and merger."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from therapist_finder.models import TherapistData
from therapist_finder.sources.arztauskunft_berlin import ArztauskunftBerlinSource
from therapist_finder.sources.base import SearchParams
from therapist_finder.sources.geocode import (
    Geocoder,
    GeocodingError,
    haversine_km,
)
from therapist_finder.sources.merger import merge_and_rank
from therapist_finder.sources.overpass import OverpassSource
from therapist_finder.sources.ptk_berlin import PTKBerlinSource

FIXTURES = Path(__file__).parent / "fixtures" / "sources"
UA = "therapist-finder-tests/0.0"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def search_params() -> SearchParams:
    """Search params anchored at Kastanienallee 12, 10435 Berlin."""
    return SearchParams(
        specialty="Psychotherapeut",
        lat=52.5396,
        lon=13.4127,
        radius_km=5.0,
        limit_per_source=20,
    )


class TestOverpassSource:
    """Tests for the OSM Overpass source."""

    def test_parses_elements(
        self, httpx_mock: HTTPXMock, search_params: SearchParams
    ) -> None:
        """It maps OSM tags into ``TherapistData`` and drops nameless elements."""
        payload = json.loads(_read("overpass.json"))
        httpx_mock.add_response(
            url="https://overpass.example/api/interpreter",
            method="POST",
            json=payload,
        )
        src = OverpassSource(
            endpoint="https://overpass.example/api/interpreter", user_agent=UA
        )
        try:
            results = src.search(search_params)
        finally:
            src.close()

        # Two valid entries (third element has empty name)
        assert len(results) == 2
        first = results[0]
        assert first.name == "Praxis Dr. Anna Beispiel"
        assert first.address == "Kastanienallee 12, 10435 Berlin"
        assert first.telefon == "+49 30 1234567"
        assert first.email == "praxis@beispiel.de"
        assert first.website == "https://praxis-beispiel.de"
        assert first.languages == ["de", "en"]
        assert first.lat == pytest.approx(52.5396)
        assert first.lon == pytest.approx(13.4127)
        assert first.sources == ["osm"]


class TestPTKBerlinSource:
    """Tests for the PTK Berlin HTML scraper."""

    def test_parses_list_and_detail(
        self, httpx_mock: HTTPXMock, search_params: SearchParams
    ) -> None:
        """List + detail pages combine into a populated ``TherapistData``."""
        httpx_mock.add_response(
            url="https://ptk.example/robots.txt", method="GET", text=""
        )
        httpx_mock.add_response(
            url="https://ptk.example/search?ort=Berlin&seite=1&verfahren=PP",
            method="GET",
            text=_read("ptk_list.html"),
        )
        httpx_mock.add_response(
            url="https://ptk.example/therapeut/anna-beispiel",
            method="GET",
            text=_read("ptk_detail.html"),
        )
        httpx_mock.add_response(
            url="https://ptk.example/therapeut/clara-kollege",
            method="GET",
            text=_read("ptk_detail.html"),
        )
        search_params.limit_per_source = 2

        src = PTKBerlinSource(
            user_agent=UA,
            base_url="https://ptk.example",
            search_path="/search",
            min_delay_seconds=0.0,
        )
        try:
            results = src.search(search_params)
        finally:
            src.close()

        assert len(results) == 2
        assert results[0].name == "Dr. Anna Beispiel"
        assert results[0].email == "praxis@beispiel.de"
        assert results[0].website == "https://praxis-beispiel.de"
        assert "Verhaltenstherapie" in results[0].therapieform
        assert results[0].languages == ["Deutsch", "Englisch"]
        assert results[0].insurance_type == "both"
        assert results[0].sources == ["ptk"]

    def test_respects_robots_txt(
        self, httpx_mock: HTTPXMock, search_params: SearchParams
    ) -> None:
        """A Disallow: / robots.txt blocks all fetching."""
        httpx_mock.add_response(
            url="https://ptk.example/robots.txt",
            method="GET",
            text="User-agent: *\nDisallow: /\n",
        )
        src = PTKBerlinSource(
            user_agent=UA,
            base_url="https://ptk.example",
            search_path="/search",
            min_delay_seconds=0.0,
        )
        try:
            assert src.search(search_params) == []
        finally:
            src.close()


class TestArztauskunftBerlinSource:
    """Tests for the Ärztekammer Berlin HTML scraper."""

    def test_parses_list_and_detail(
        self, httpx_mock: HTTPXMock, search_params: SearchParams
    ) -> None:
        """Specialty param maps to 'Psychiatrie' and detail fields populate."""
        httpx_mock.add_response(
            url="https://aeka.example/robots.txt", method="GET", text=""
        )
        httpx_mock.add_response(
            url="https://aeka.example/suche?fachgebiet=Psychiatrie&ort=Berlin&seite=1",
            method="GET",
            text=_read("aeka_list.html"),
        )
        httpx_mock.add_response(
            url="https://aeka.example/arzt/bernd-muster",
            method="GET",
            text=_read("aeka_detail.html"),
        )
        search_params.specialty = "Psychiater"
        search_params.limit_per_source = 1

        src = ArztauskunftBerlinSource(
            user_agent=UA,
            base_url="https://aeka.example",
            search_path="/suche",
            min_delay_seconds=0.0,
        )
        try:
            results = src.search(search_params)
        finally:
            src.close()

        assert len(results) == 1
        entry = results[0]
        assert entry.name == "Dr. med. Bernd Muster"
        assert entry.email == "bernd@muster-praxis.de"
        assert "Psychiatrie" in entry.therapieform
        assert entry.sources == ["aeka"]


class TestGeocoder:
    """Tests for the Nominatim geocoder wrapper."""

    def test_geocode_success(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        """A Berlin address returns a ``Location`` and caches the response."""
        httpx_mock.add_response(
            url=httpx.URL(
                "https://nominatim.example/search",
                params={
                    "q": "Kastanienallee 12, 10435 Berlin",
                    "format": "jsonv2",
                    "limit": "1",
                    "addressdetails": "1",
                    "countrycodes": "de",
                },
            ),
            method="GET",
            json=[
                {
                    "lat": "52.5396",
                    "lon": "13.4127",
                    "display_name": "Kastanienallee 12, 10435 Berlin, Germany",
                }
            ],
        )
        geocoder = Geocoder(
            endpoint="https://nominatim.example/search",
            user_agent=UA,
            cache_dir=tmp_path,
        )
        try:
            loc = geocoder.geocode("Kastanienallee 12, 10435 Berlin")
        finally:
            geocoder.close()
        assert loc.lat == pytest.approx(52.5396)
        assert loc.lon == pytest.approx(13.4127)

    def test_geocode_outside_berlin_raises(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        """Resolved coords outside Berlin → ``GeocodingError``."""
        httpx_mock.add_response(
            method="GET",
            json=[{"lat": "48.1374", "lon": "11.5755", "display_name": "Munich"}],
        )
        geocoder = Geocoder(
            endpoint="https://nominatim.example/search",
            user_agent=UA,
            cache_dir=tmp_path,
        )
        try:
            with pytest.raises(GeocodingError):
                geocoder.geocode("Marienplatz, München")
        finally:
            geocoder.close()

    def test_haversine_symmetry(self) -> None:
        """Haversine is symmetric and zero for identical points."""
        assert haversine_km(52.52, 13.40, 52.52, 13.40) == pytest.approx(0.0)
        d1 = haversine_km(52.52, 13.40, 52.54, 13.42)
        d2 = haversine_km(52.54, 13.42, 52.52, 13.40)
        assert d1 == pytest.approx(d2)


class TestMerger:
    """Tests for the cross-source merger."""

    def test_merges_and_sorts_by_distance(self) -> None:
        """Duplicate across sources collapses, results sort by distance asc."""
        origin_lat, origin_lon = 52.5396, 13.4127
        near = TherapistData(
            name="Dr. Anna Beispiel",
            address="Kastanienallee 12, 10435 Berlin",
            email="praxis@beispiel.de",
            lat=52.5396,
            lon=13.4127,
            sources=["osm"],
        )
        near_dup = TherapistData(
            name="Anna Beispiel",
            address="Kastanienallee 12, 10435 Berlin",
            telefon="030 1234567",
            sources=["ptk"],
        )
        far = TherapistData(
            name="Dr. Weit Entfernt",
            address="Wilhelmstraße 5, 12247 Berlin",
            lat=52.45,
            lon=13.36,
            sources=["116117"],
        )

        merged = merge_and_rank(
            {"osm": [near], "ptk": [near_dup], "116117": [far]},
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            limit=10,
        )

        assert len(merged) == 2
        first = merged[0]
        assert first.name == "Dr. Anna Beispiel"
        assert first.telefon == "030 1234567"
        assert first.email == "praxis@beispiel.de"
        assert sorted(first.sources) == ["osm", "ptk"]
        assert first.distance_km == pytest.approx(0.0, abs=0.05)
        assert merged[1].name == "Dr. Weit Entfernt"
        assert merged[1].distance_km is not None
        assert merged[1].distance_km > first.distance_km  # type: ignore[operator]

    def test_limit_truncates_sorted_results(self) -> None:
        """``limit`` applies after sorting, not per-source."""
        providers = [
            TherapistData(
                name=f"Doc {i}",
                address=f"Test {i}, 10{i:03d} Berlin",
                lat=52.52 + i * 0.01,
                lon=13.40,
                sources=["osm"],
            )
            for i in range(5)
        ]
        merged = merge_and_rank(
            {"osm": providers},
            origin_lat=52.52,
            origin_lon=13.40,
            limit=3,
        )
        assert [p.name for p in merged] == ["Doc 0", "Doc 1", "Doc 2"]
