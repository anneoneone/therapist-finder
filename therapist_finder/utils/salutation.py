"""Build a German salutation line from a therapist's full name."""

from __future__ import annotations

import re

from .gender import guess_gender

_TITLE_RE = re.compile(r"(Dr\.|Dipl\.-Psych\.|Prof\.)")
_TITLE_TOKENS = {"Dr.", "Dipl.-Psych.", "Prof.", "Med.", "Frau", "Herr"}


def make_salutation(name: str) -> str:
    """Return a 'Sehr geehrte/r ...' line for the given full name.

    Honors explicit 'Frau'/'Herr' markers if present; otherwise guesses
    gender from the first name. Falls back to a neutral greeting when
    the guess is inconclusive.
    """
    if not name:
        return "Sehr geehrte Damen und Herren"

    title_match = _TITLE_RE.search(name)
    title = title_match.group(0) if title_match else ""
    parts = name.split()
    last_name = parts[-1] if parts else ""

    if "Frau" in parts:
        gender = "female"
    elif "Herr" in parts:
        gender = "male"
    else:
        gender = guess_gender(_extract_first_name(parts))

    if gender == "female":
        return _join("Sehr geehrte Frau", title, last_name)
    if gender == "male":
        return _join("Sehr geehrter Herr", title, last_name)
    return _join("Guten Tag", title, last_name)


def _extract_first_name(parts: list[str]) -> str:
    """Pick the first token that looks like a usable first name."""
    for part in parts[:-1]:
        if part in _TITLE_TOKENS:
            continue
        if part.endswith(".") and len(part) <= 3:
            continue
        return part.strip(",")
    return ""


def _join(*tokens: str) -> str:
    return " ".join(t for t in tokens if t)
