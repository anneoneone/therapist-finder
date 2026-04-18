"""Registry of normalized doctor specialties.

The upstream directories each describe specialties in their own dialect
(OSM ``healthcare:speciality`` values, psych-info ``verfahren`` codes, the
116117 German "Fachgebiet" labels, and free-text in scraped HTML). This
module is the single place that maps those dialects onto a small set of
stable keys the UI can offer as a dropdown.

For each specialty we store:

* ``key``:            stable slug used by the API / frontend.
* ``label``:          German display label for the dropdown.
* ``osm_values``:     regex alternatives for the OSM ``healthcare`` /
                      ``healthcare:speciality`` tag. Also used to decide
                      which OSM ``amenity=doctors`` hits are relevant.
* ``de_label``:       the German chamber label for 116117 requests.
* ``verfahren``:      psych-info ``verfahren`` query parameter value.
* ``match_patterns``: regex patterns applied to a therapist's name /
                      therapieform to post-filter results that an upstream
                      source returned unfiltered (e.g. OSM's generic
                      ``amenity=doctors``).
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from therapist_finder.models import TherapistData

_ALL_KEY = "all"


@dataclass(frozen=True)
class Specialty:
    """A normalized doctor kind offered in the search UI."""

    key: str
    label: str
    osm_values: tuple[str, ...]
    de_label: str
    verfahren: str = ""
    match_patterns: tuple[str, ...] = ()


# Ordered: the frontend displays them in this order.
_SPECIALTIES: tuple[Specialty, ...] = (
    Specialty(
        key=_ALL_KEY,
        label="Alle Ärzte & Therapeut:innen",
        osm_values=("psychotherapist", "doctor", "psychiatrist"),
        de_label="Arzt",
        match_patterns=(),
    ),
    Specialty(
        key="psychotherapie",
        label="Psychotherapie",
        osm_values=("psychotherapist", "psychotherapy"),
        de_label="Psychotherapeut",
        verfahren="PP",
        match_patterns=(
            r"psychotherap",
            r"verhaltensther",
            r"tiefenpsycholog",
            r"\bpp\b",
        ),
    ),
    Specialty(
        key="kinder_jugend_psychotherapie",
        label="Kinder- & Jugendpsychotherapie",
        osm_values=("psychotherapist",),
        de_label="Kinder- und Jugendlichenpsychotherapeut",
        verfahren="KJP",
        match_patterns=(
            r"kinder[- ]?(und[- ]?)?jugend.*psychotherap",
            r"kinder.*jugend.*therap",
            r"\bkjp\b",
        ),
    ),
    Specialty(
        key="psychiatrie",
        label="Psychiatrie",
        osm_values=("psychiatrist", "psychiatry"),
        de_label="Psychiater",
        match_patterns=(r"psychiat", r"nervenarzt", r"nervenheil"),
    ),
    Specialty(
        key="kinderarzt",
        label="Kinder- & Jugendmedizin",
        osm_values=("pediatrics", "paediatrics"),
        de_label="Kinder- und Jugendmediziner",
        match_patterns=(
            r"kinder[- ]?(und[- ]?)?jugendmedizin",
            r"kinderarzt",
            r"kinderheilkunde",
            r"p(ä|ae)diatr",
            r"familienmedizin",
        ),
    ),
    Specialty(
        key="allgemeinmedizin",
        label="Allgemeinmedizin / Hausarzt",
        osm_values=("general", "general_practitioner", "doctor"),
        de_label="Allgemeinmediziner",
        match_patterns=(
            r"allgemeinmedizin",
            r"hausarzt",
            r"praktischer\s+arzt",
        ),
    ),
    Specialty(
        key="hno",
        label="HNO (Hals-Nasen-Ohren)",
        osm_values=("otolaryngology", "ear_nose_throat"),
        de_label="HNO-Arzt",
        match_patterns=(r"\bhno\b", r"hals.nasen", r"otolaryng"),
    ),
    Specialty(
        key="gynaekologie",
        label="Gynäkologie",
        osm_values=("gynaecology", "gynecology", "obstetrics"),
        de_label="Frauenarzt",
        match_patterns=(r"gyn(ä|ae)kolog", r"frauenheil", r"geburtshilfe"),
    ),
    Specialty(
        key="dermatologie",
        label="Dermatologie (Haut)",
        osm_values=("dermatology",),
        de_label="Dermatologe",
        match_patterns=(r"dermatolog", r"hautarzt", r"hautheilkunde"),
    ),
    Specialty(
        key="augenarzt",
        label="Augenheilkunde",
        osm_values=("ophthalmology",),
        de_label="Augenarzt",
        match_patterns=(r"ophthalmolog", r"augenarzt", r"augenheil"),
    ),
    Specialty(
        key="orthopaedie",
        label="Orthopädie",
        osm_values=("orthopaedics", "orthopedics"),
        de_label="Orthopäde",
        match_patterns=(r"orthop(ä|ae)d",),
    ),
    Specialty(
        key="zahnarzt",
        label="Zahnarzt",
        osm_values=("dentist",),
        de_label="Zahnarzt",
        match_patterns=(r"zahnarzt", r"zahnheilkunde", r"\bdental\b"),
    ),
    Specialty(
        key="heilpraktiker",
        label="Heilpraktiker:in (Psychotherapie)",
        osm_values=("alternative", "psychotherapist"),
        de_label="Heilpraktiker",
        match_patterns=(r"heilpraktiker",),
    ),
)

SPECIALTIES: dict[str, Specialty] = {s.key: s for s in _SPECIALTIES}
DEFAULT_KEY = "psychotherapie"


def all_specialties() -> tuple[Specialty, ...]:
    """Return the registered specialties in display order."""
    return _SPECIALTIES


def resolve(key_or_label: str | None) -> Specialty:
    """Resolve ``key_or_label`` (slug or legacy German label) to a Specialty.

    Falls back to the default specialty when the input is empty or unknown.
    Accepts legacy German labels like ``"Psychotherapeut"`` so existing
    clients keep working.
    """
    if not key_or_label:
        return SPECIALTIES[DEFAULT_KEY]
    raw = key_or_label.strip()
    lowered = raw.lower()
    if lowered in SPECIALTIES:
        return SPECIALTIES[lowered]
    for spec in _SPECIALTIES:
        if spec.de_label.lower() == lowered:
            return spec
        if spec.label.lower() == lowered:
            return spec
    # Heuristic: substring match against German label / key.
    for spec in _SPECIALTIES:
        if lowered in spec.de_label.lower() or lowered in spec.key:
            return spec
    return SPECIALTIES[DEFAULT_KEY]


def is_all(spec: Specialty) -> bool:
    """Whether ``spec`` is the catch-all option (no filtering)."""
    return spec.key == _ALL_KEY


def _haystack(therapist: TherapistData) -> str:
    parts: list[str] = [therapist.name or ""]
    parts.extend(therapist.therapieform or [])
    if therapist.salutation:
        parts.append(therapist.salutation)
    return " ".join(parts).lower()


def matches(spec: Specialty, therapist: TherapistData) -> bool:
    """Return True if ``therapist`` looks like ``spec``.

    The catch-all specialty always matches. Otherwise we look for any of
    the specialty's ``match_patterns`` in the therapist's name +
    therapieform + salutation. Entries that don't obviously belong to any
    specialty fall through as non-matches for every specific filter, which
    is the right default — users who want "everything" pick ``all``.
    """
    if is_all(spec):
        return True
    if not spec.match_patterns:
        return True
    text = _haystack(therapist)
    if not text.strip():
        return False
    return any(re.search(pat, text) for pat in spec.match_patterns)


def infer_key(therapist: TherapistData) -> str | None:
    """Infer the specialty key for a therapist from its text fields.

    Returns the first specialty whose ``match_patterns`` hit, or ``None``
    if nothing matched. Used to tag normalised results in API responses.
    """
    text = _haystack(therapist)
    if not text.strip():
        return None
    for spec in _SPECIALTIES:
        if is_all(spec):
            continue
        if any(re.search(pat, text) for pat in spec.match_patterns):
            return spec.key
    return None


def filter_results(
    spec: Specialty, therapists: list[TherapistData]
) -> list[TherapistData]:
    """Drop entries that don't look like ``spec``. No-op for the catch-all."""
    if is_all(spec):
        return therapists
    return [t for t in therapists if matches(spec, t)]
