#!/usr/bin/env python3
"""Pre-translate the UI dictionary using the DeepL API.

Reads `frontend/js/i18n/en.json` (source) and writes one translated JSON
file per target language alongside it.

Requires the `DEEPL_API_KEY` environment variable. Works with both the
free (api-free.deepl.com) and pro (api.deepl.com) endpoints — the script
detects which based on the key suffix.

Run after editing en.json:

    DEEPL_API_KEY=... python scripts/translate_ui.py

Pass --langs ar,tr to translate a subset; --force to overwrite existing
files (default skips languages whose file already exists).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = REPO_ROOT / "frontend" / "js" / "i18n"
SOURCE_FILE = I18N_DIR / "en.json"

# DeepL target-language codes (uppercase). Some need explicit variants.
TARGET_LANGS: dict[str, dict[str, str]] = {
    "de": {"deepl": "DE", "name": "German", "nativeName": "Deutsch", "dir": "ltr"},
    "fr": {"deepl": "FR", "name": "French", "nativeName": "Français", "dir": "ltr"},
    "ar": {"deepl": "AR", "name": "Arabic", "nativeName": "العربية", "dir": "rtl"},
    "tr": {"deepl": "TR", "name": "Turkish", "nativeName": "Türkçe", "dir": "ltr"},
    "es": {"deepl": "ES", "name": "Spanish", "nativeName": "Español", "dir": "ltr"},
    "it": {"deepl": "IT", "name": "Italian", "nativeName": "Italiano", "dir": "ltr"},
    "ru": {"deepl": "RU", "name": "Russian", "nativeName": "Русский", "dir": "ltr"},
}

# Tokens we never want DeepL to translate. We replace them with placeholder
# IDs before sending, then restore them after.
#   - {placeholder}   (curly-brace interpolation, e.g. {total}, {name})
#   - <ANREDE>        (literal template marker — must stay verbatim)
#   - <code>...</code> and other HTML tags (handled by tag_handling="html")
PROTECTED_PATTERNS = [
    re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}"),
    re.compile(r"<ANREDE>"),
]


def protect(text: str) -> tuple[str, list[str]]:
    """Replace protected tokens with `<x id="0"/>` placeholders.

    DeepL's tag_handling=html mode leaves `<x .../>` tags verbatim, so this
    is a reliable way to keep `{name}`, `<ANREDE>`, etc. untranslated.
    """
    tokens: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        idx = len(tokens)
        tokens.append(match.group(0))
        return f'<x id="{idx}"/>'

    out = text
    for pattern in PROTECTED_PATTERNS:
        out = pattern.sub(_replace, out)
    return out, tokens


def unprotect(text: str, tokens: list[str]) -> str:
    """Restore tokens replaced by `protect`."""
    out = text
    for idx, token in enumerate(tokens):
        out = out.replace(f'<x id="{idx}"/>', token)
    return out


def deepl_endpoint(api_key: str) -> str:
    """Return the DeepL endpoint matching the key tier (free vs pro)."""
    # DeepL convention: free keys end in ":fx".
    if api_key.endswith(":fx"):
        return "https://api-free.deepl.com/v2/translate"
    return "https://api.deepl.com/v2/translate"


def translate_batch(texts: list[str], target_lang: str, api_key: str) -> list[str]:
    """Translate a batch of strings via DeepL. Preserves order."""
    if not texts:
        return []

    data = [
        ("source_lang", "EN"),
        ("target_lang", target_lang),
        ("tag_handling", "html"),
        ("preserve_formatting", "1"),
    ]
    for text in texts:
        data.append(("text", text))

    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        deepl_endpoint(api_key),
        data=body,
        headers={
            "Authorization": f"DeepL-Auth-Key {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "therapist-finder-ui-translator/1.0",
        },
        method="POST",
    )
    try:
        # B310/S310: hard-coded https://api[-free].deepl.com endpoint,
        # not user-controlled — no file:// or other-scheme exposure.
        urlopen = urllib.request.urlopen  # noqa: S310
        with urlopen(req, timeout=60) as resp:  # nosec B310
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(
            f"DeepL HTTP {exc.code} for {target_lang}: {detail}"
        ) from exc

    translations = payload.get("translations", [])
    if len(translations) != len(texts):
        raise RuntimeError(
            f"DeepL returned {len(translations)} translations, expected {len(texts)}"
        )
    return [t["text"] for t in translations]


def translate_dict(
    source: dict[str, Any], lang_code: str, lang_meta: dict[str, str], api_key: str
) -> dict[str, Any]:
    """Translate every string value in `source` (skipping `_meta`)."""
    keys: list[str] = []
    originals: list[str] = []
    token_lists: list[list[str]] = []

    for key, value in source.items():
        if key == "_meta" or not isinstance(value, str):
            continue
        protected, tokens = protect(value)
        keys.append(key)
        originals.append(protected)
        token_lists.append(tokens)

    print(f"  → {lang_meta['deepl']}: {len(originals)} strings")
    translated = translate_batch(originals, lang_meta["deepl"], api_key)

    out: dict[str, Any] = {
        "_meta": {
            "code": lang_code,
            "name": lang_meta["name"],
            "nativeName": lang_meta["nativeName"],
            "dir": lang_meta["dir"],
        }
    }
    for key, text, tokens in zip(keys, translated, token_lists, strict=True):
        out[key] = unprotect(text, tokens)
    return out


def main() -> int:
    """CLI entry point: translate `en.json` into requested target languages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--langs",
        default=",".join(TARGET_LANGS),
        help=f"Comma-separated list of target languages (default: {','.join(TARGET_LANGS)})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files (default: skip languages already translated).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("DEEPL_API_KEY", "").strip()
    if not api_key:
        print("error: DEEPL_API_KEY env var is required", file=sys.stderr)
        return 2

    if not SOURCE_FILE.exists():
        print(f"error: source file not found: {SOURCE_FILE}", file=sys.stderr)
        return 2

    source = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    requested = [code.strip() for code in args.langs.split(",") if code.strip()]
    unknown = [code for code in requested if code not in TARGET_LANGS]
    if unknown:
        print(f"error: unknown language codes: {unknown}", file=sys.stderr)
        return 2

    for code in requested:
        out_path = I18N_DIR / f"{code}.json"
        if out_path.exists() and not args.force:
            print(f"  ⊘ {code}: already exists (use --force to overwrite)")
            continue

        print(f"Translating → {code}")
        translated = translate_dict(source, code, TARGET_LANGS[code], api_key)
        out_path.write_text(
            json.dumps(translated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  ✓ wrote {out_path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
