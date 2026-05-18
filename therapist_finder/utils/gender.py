"""Guess gender from a first name for use in greetings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from gender_guesser.detector import Detector

Gender = Literal["female", "male", "unknown"]

_detector = Detector(case_sensitive=False)


@lru_cache(maxsize=4096)
def guess_gender(first_name: str) -> Gender:
    """Return 'female', 'male', or 'unknown' for the given first name.

    Wraps `gender_guesser` and collapses its 'mostly_*' answers into the
    confident variant. 'andy' (androgynous) and unknown names return
    'unknown', which the caller should render with a neutral greeting.
    """
    if not first_name:
        return "unknown"
    result = _detector.get_gender(first_name)
    if result in ("female", "mostly_female"):
        return "female"
    if result in ("male", "mostly_male"):
        return "male"
    return "unknown"
