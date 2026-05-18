"""Prompt template for the AI mail-body generator (issue #20)."""

from __future__ import annotations

# System instruction: kept in German because the typical recipient is a
# German-speaking practice. The model is asked to honour the user-chosen
# target language for the actual body.
SYSTEM_INSTRUCTION = (
    "Du verfasst eine kurze, sachliche Anfrage an eine psychotherapeutische "
    "Praxis im Auftrag eines Therapieplatz-Suchenden. "
    "Halte dich strikt an folgende Regeln:\n"
    "- Schreibe AUSSCHLIESSLICH in der vom Nutzer angegebenen Sprache.\n"
    "- Maximal 5 bis 7 Sätze. Klar, höflich, sachlich, keine Floskeln.\n"
    "- Inhaltlich: Anliegen einer Therapieplatz-Anfrage, Versicherungsstatus "
    "(falls genannt), Bitte um Rückmeldung zu Wartezeit und freien Plätzen.\n"
    "- Erfinde KEINE Diagnosen, Symptome oder persönlichen Details.\n"
    "- Wenn bereits frühere Mails an dieselbe Praxis vorliegen, formuliere "
    "deutlich anders (Satzbau, Reihenfolge, Wortwahl).\n"
    "- Gib NUR den reinen Mail-Body zurück: KEINE Anrede, KEINE Grußformel, "
    "KEINE Unterschrift, KEINE Betreffzeile. Anrede und Abschluss werden "
    "separat eingefügt."
)


def build_user_prompt(
    *,
    target_lang: str,
    insurance: str | None,
    prior_bodies: list[str],
) -> str:
    """Render the per-request user prompt."""
    lang = (target_lang or "de").strip() or "de"
    ins = (insurance or "").strip() or "nicht angegeben"
    if prior_bodies:
        prior_block = "\n\n---\n\n".join(b.strip() for b in prior_bodies if b.strip())
        prior_section = (
            "Bereits an diese Praxis gesendete Mails "
            "(nicht wiederholen, anders formulieren):\n\n"
            f"{prior_block}"
        )
    else:
        prior_section = "Bereits an diese Praxis gesendete Mails: keine."
    return (
        f"Sprache des Mail-Bodys: {lang}\n"
        f"Versicherung: {ins}\n\n"
        f"{prior_section}\n\n"
        "Schreibe jetzt den Mail-Body."
    )
