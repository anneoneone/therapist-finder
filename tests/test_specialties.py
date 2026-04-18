"""Tests for the normalized specialty registry."""

from __future__ import annotations

import pytest

from therapist_finder.models import TherapistData
from therapist_finder.sources import specialties


def _mk(name: str, *therapieform: str) -> TherapistData:
    return TherapistData(name=name, therapieform=list(therapieform))


class TestResolve:
    def test_resolves_by_slug(self) -> None:
        assert specialties.resolve("psychotherapie").key == "psychotherapie"
        assert specialties.resolve("hno").key == "hno"
        assert specialties.resolve("all").key == "all"

    def test_resolves_legacy_german_label(self) -> None:
        """Old clients sending ``'Psychotherapeut'`` still get the right spec."""
        assert specialties.resolve("Psychotherapeut").key == "psychotherapie"
        assert specialties.resolve("Psychiater").key == "psychiatrie"

    def test_empty_falls_back_to_default(self) -> None:
        assert specialties.resolve("").key == specialties.DEFAULT_KEY
        assert specialties.resolve(None).key == specialties.DEFAULT_KEY

    def test_unknown_falls_back_to_default(self) -> None:
        assert specialties.resolve("totally-unknown-xyz").key == specialties.DEFAULT_KEY


class TestMatches:
    @pytest.mark.parametrize(
        ("specialty_key", "therapist", "expected"),
        [
            ("psychotherapie", _mk("Psychotherapeutische Praxis"), True),
            ("psychotherapie", _mk("HNO-Praxis Kreuzberg-Süd"), False),
            ("hno", _mk("HNO-Praxis Kreuzberg-Süd"), True),
            ("hno", _mk("Praxis für Hals-Nasen-Ohrenheilkunde"), True),
            (
                "kinderarzt",
                _mk("Praxis für Kinder-, Jugend- und Familienmedizin"),
                True,
            ),
            ("psychiatrie", _mk("FÄ für Psychiatrie und Psychotherapie"), True),
            (
                "kinder_jugend_psychotherapie",
                _mk("Praxis für Kinder- und Jugendpsychotherapie"),
                True,
            ),
            ("kinder_jugend_psychotherapie", _mk("Allgemeine Psychiatrie"), False),
            ("all", _mk("Anything at all"), True),
        ],
    )
    def test_matches(
        self, specialty_key: str, therapist: TherapistData, expected: bool
    ) -> None:
        spec = specialties.SPECIALTIES[specialty_key]
        assert specialties.matches(spec, therapist) is expected


class TestInferKey:
    def test_infers_hno_from_name(self) -> None:
        assert specialties.infer_key(_mk("HNO-Praxis Kreuzberg")) == "hno"

    def test_infers_psychotherapie_from_therapieform(self) -> None:
        t = _mk("Dr. Beispiel", "Verhaltenstherapie")
        assert specialties.infer_key(t) == "psychotherapie"

    def test_unknown_returns_none(self) -> None:
        assert specialties.infer_key(_mk("Gemeinschaftspraxis Dr. Pustelnik")) is None


class TestFilterResults:
    def test_filters_out_non_matching(self) -> None:
        spec = specialties.SPECIALTIES["psychotherapie"]
        therapists = [
            _mk("Psychotherapeutische Praxis"),
            _mk("HNO-Praxis Kreuzberg-Süd"),
            _mk("Praxis für Kinder-, Jugend- und Familienmedizin"),
        ]
        filtered = specialties.filter_results(spec, therapists)
        assert [t.name for t in filtered] == ["Psychotherapeutische Praxis"]

    def test_all_is_passthrough(self) -> None:
        spec = specialties.SPECIALTIES["all"]
        therapists = [_mk("HNO-Praxis"), _mk("Dr. Beispiel")]
        assert specialties.filter_results(spec, therapists) == therapists
