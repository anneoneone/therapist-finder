"""Gemini-backed mail body generator (issue #19).

Exposes a single function, :func:`generate_mail_body`, plus a typed
:class:`AiUnavailableError` raised when the ``GEMINI_API_KEY`` env var is
missing or the SDK is not installed. The route layer maps this to a 503.

The generator deliberately receives NO PII: the existing template
machinery substitutes greeting, contact info, and closing after the body
is produced.
"""

from __future__ import annotations

import os
import re

from .prompts import SYSTEM_INSTRUCTION, build_user_prompt

# Default to gemini-2.5-flash-lite: the current free-tier model with the
# most generous quota for short text generation. gemini-2.0-flash was
# retired from the free tier (limit=0). Overridable via env so the model
# can be swapped without a deploy when Google rotates quotas again.
_DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Strip accidental greetings/closings if the model includes them anyway.
# Matches the most common German/English variants at line start or end.
_GREETING_RE = re.compile(
    r"^(sehr geehrte[rn]?\b|hallo\b|guten tag\b|liebe[rn]?\b|dear\b).*$",
    re.IGNORECASE,
)
_CLOSING_RE = re.compile(
    r"^(mit freundlichen gr[üu][ßs]en|freundliche gr[üu][ßs]e|"
    r"viele gr[üu][ßs]e|beste gr[üu][ßs]e|"
    r"kind regards|best regards|sincerely)\b.*$",
    re.IGNORECASE,
)


class AiUnavailableError(RuntimeError):
    """Raised when AI generation cannot run (no key, SDK missing, etc.)."""


def _strip_boilerplate(text: str) -> str:
    """Drop greeting/closing lines the model may have added despite instructions."""
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    # Drop greeting line at the top (plus any leading blank lines).
    while lines and (not lines[0].strip() or _GREETING_RE.match(lines[0].strip())):
        lines.pop(0)
    # If a closing line exists, truncate it AND every line after it (signature).
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped and _CLOSING_RE.match(stripped):
            lines = lines[:i]
            break
    # Trim trailing blanks.
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def generate_mail_body(
    *,
    target_lang: str,
    insurance: str | None,
    prior_bodies: list[str],
) -> str:
    """Generate a therapist-inquiry mail body via Gemini 2.0 Flash.

    Args:
        target_lang: Language code/name for the output body (e.g. "de", "en").
        insurance: User-stated insurance label ("gesetzlich", "privat", ...).
            None means "not specified".
        prior_bodies: Previously sent mail bodies (any therapist of this
            send-batch). The model is told to vary phrasing against these.

    Returns:
        The cleaned mail body, ready to drop into ``state.templateBody``.

    Raises:
        AiUnavailableError: If ``GEMINI_API_KEY`` is unset or the SDK is
            not installed. The route turns this into HTTP 503.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise AiUnavailableError(
            "GEMINI_API_KEY is not set; AI mail generation is unavailable."
        )

    try:
        # Pre-commit's isolated mypy env doesn't install google-genai, so a
        # tight ``[import-untyped]`` ignore doesn't cover its
        # ``import-not-found`` error code. A broad ignore here is fine: the
        # SDK ships no stubs anyway.
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError as exc:  # pragma: no cover - dep is in pyproject
        raise AiUnavailableError(
            "google-genai SDK is not installed; cannot generate AI mail."
        ) from exc

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)
    response = client.models.generate_content(
        model=model,
        contents=build_user_prompt(
            target_lang=target_lang,
            insurance=insurance,
            prior_bodies=prior_bodies,
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
            max_output_tokens=600,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise AiUnavailableError("AI returned an empty response.")
    return _strip_boilerplate(text)
