"""Tests for healthcare-provider data sources and merger."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from therapist_finder.models import TherapistData
from therapist_finder.sources.base import SearchParams
from therapist_finder.sources.geocode import (
    Geocoder,
    GeocodingError,
    haversine_km,
)
from therapist_finder.sources.merger import merge_and_rank
from therapist_finder.sources.overpass import OverpassSource
from therapist_finder.sources.psych_info import PsychInfoSource
from therapist_finder.sources.therapie_de import TherapieDeSource

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


class TestPsychInfoSource:
    """Tests for the psych-info.de HTML scraper (residential only)."""

    def test_parses_list_and_detail(
        self, httpx_mock: HTTPXMock, search_params: SearchParams
    ) -> None:
        """List + detail pages combine into a populated ``TherapistData``."""
        httpx_mock.add_response(
            url="https://psych.example/robots.txt", method="GET", text=""
        )
        httpx_mock.add_response(
            url="https://psych.example/suche?ort=Berlin&verfahren=PP&seite=1",
            method="GET",
            text=_read("psych_info_list.html"),
        )
        httpx_mock.add_response(
            url="https://psych.example/therapeut/anna-beispiel",
            method="GET",
            text=_read("psych_info_detail.html"),
        )
        httpx_mock.add_response(
            url="https://psych.example/therapeut/clara-kollege",
            method="GET",
            text=_read("psych_info_detail.html"),
        )
        search_params.limit_per_source = 2

        src = PsychInfoSource(
            user_agent=UA,
            base_url="https://psych.example",
            min_delay_seconds=0.0,
        )
        try:
            results = src.search(search_params)
        finally:
            src.close()

        assert len(results) == 2
        first = results[0]
        assert first.name == "Dr. Anna Beispiel"
        assert first.email == "praxis@beispiel.de"
        assert first.website == "https://praxis-beispiel.de"
        assert "Verhaltenstherapie" in first.therapieform
        assert first.languages == ["Deutsch", "Englisch"]
        assert first.insurance_type == "privat"
        assert first.sources == ["psych_info"]

    def test_respects_robots_txt(
        self, httpx_mock: HTTPXMock, search_params: SearchParams
    ) -> None:
        """A Disallow: / robots.txt blocks all fetching."""
        httpx_mock.add_response(
            url="https://psych.example/robots.txt",
            method="GET",
            text="User-agent: *\nDisallow: /\n",
        )
        src = PsychInfoSource(
            user_agent=UA,
            base_url="https://psych.example",
            min_delay_seconds=0.0,
        )
        try:
            assert src.search(search_params) == []
        finally:
            src.close()


class TestTherapieDeSource:
    """Tests for the therapie.de HTML scraper (residential only)."""

    def test_parses_and_flags_heilpraktiker(
        self, httpx_mock: HTTPXMock, search_params: SearchParams
    ) -> None:
        """Detail text with 'Heilpraktikerin' → insurance_type 'heilpraktiker'."""
        httpx_mock.add_response(
            url="https://therapiede.example/robots.txt", method="GET", text=""
        )
        httpx_mock.add_response(
            url="https://therapiede.example/psychotherapie/-ort-/berlin/",
            method="GET",
            text=_read("therapie_de_list.html"),
        )
        httpx_mock.add_response(
            url="https://therapiede.example/therapeut/mia-mueller",
            method="GET",
            text=_read("therapie_de_detail.html"),
        )
        httpx_mock.add_response(
            url="https://therapiede.example/therapeut/lea-lotus",
            method="GET",
            text=_read("therapie_de_detail.html"),
        )
        search_params.limit_per_source = 2

        src = TherapieDeSource(
            user_agent=UA,
            base_url="https://therapiede.example",
            listing_path="/psychotherapie/-ort-/berlin",
            min_delay_seconds=0.0,
        )
        try:
            results = src.search(search_params)
        finally:
            src.close()

        assert len(results) == 2
        heilpraktikerin = next(r for r in results if "Lotus" in r.name)
        assert heilpraktikerin.insurance_type == "heilpraktiker"
        assert heilpraktikerin.email == "kontakt@lotus-praxis.de"
        assert heilpraktikerin.website == "https://lotus-praxis.de"
        assert heilpraktikerin.sources == ["therapie_de"]


class TestGeocoder:
    """Tests for the Photon + Nominatim geocoder wrapper."""

    def test_nominatim_success(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        """Nominatim endpoint parses the flat-list response shape."""
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

    def test_photon_success(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        """Photon endpoint parses the GeoJSON FeatureCollection response."""
        httpx_mock.add_response(
            url=httpx.URL(
                "https://photon.example/api/",
                params={
                    "q": "Kastanienallee 12, 10435 Berlin",
                    "limit": "1",
                    "lang": "de",
                },
            ),
            method="GET",
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [13.4127, 52.5396],
                        },
                        "properties": {
                            "street": "Kastanienallee",
                            "housenumber": "12",
                            "postcode": "10435",
                            "city": "Berlin",
                        },
                    }
                ],
            },
        )
        geocoder = Geocoder(
            endpoint="https://photon.example/api/",
            user_agent=UA,
            cache_dir=tmp_path,
        )
        try:
            loc = geocoder.geocode("Kastanienallee 12, 10435 Berlin")
        finally:
            geocoder.close()
        assert loc.lat == pytest.approx(52.5396)
        assert loc.lon == pytest.approx(13.4127)
        assert "Kastanienallee" in loc.display_name

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
