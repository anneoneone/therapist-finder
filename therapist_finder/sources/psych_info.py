"""Scraper for the Psych-Info therapist register.

Psych-Info (``psych-info.de``) is a voluntary directory maintained by six
German Landespsychotherapeutenkammern (incl. Berlin). The Psychotherapeuten-
kammer Berlin delegates its "Psychotherapeut:innensuche" to this site, so it
is the correct source to add for private-pay Approbierte that 116117 misses.

**Residential only.** psych-info.de actively blocks cloud/datacenter IPs via
WAF — running this from a CI runner will get 403 or "Sie haben leider keinen
Zugriff" pages. Run from the user's laptop.

CSS selectors below are best-effort placeholders. The real HTML structure
needs to be captured once from a residential IP (see
``scripts/recon_sources.py``); feed the captured HTML into
``_parse_list_page`` / ``_parse_detail_page`` in tests to calibrate.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from therapist_finder.models import InsuranceType, TherapistData
from therapist_finder.sources._html_scraper import (
    HTMLScraper,
    ListEntry,
    clean,
    extract_email_from_html,
    extract_external_website,
    extract_link,
    extract_list,
    text_of,
)
from therapist_finder.sources.base import SearchParams

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://psych-info.de"


class PsychInfoSource(HTMLScraper):
    """HTML scraper for psych-info.de (residential IP required)."""

    name = "psych_info"

    def __init__(
        self,
        user_agent: str,
        base_url: str = _DEFAULT_BASE,
        min_delay_seconds: float = 2.5,
        client: object | None = None,
        respect_robots_txt: bool = True,
    ) -> None:
        """Initialise. ``client`` is an ``httpx.Client`` (typed loose for mocks)."""
        super().__init__(
            user_agent=user_agent,
            base_url=base_url,
            min_delay_seconds=min_delay_seconds,
            client=client,  # type: ignore[arg-type]
            respect_robots_txt=respect_robots_txt,
        )

    def _iter_list_urls(self, params: SearchParams) -> list[str]:
        # psych-info search takes an ``ort`` (city/PLZ) query parameter; the
        # exact path isn't publicly documented, so we keep it configurable.
        pages = max(1, (params.limit_per_source + 19) // 20)
        return [
            f"{self.base_url}/suche?ort=Berlin&verfahren={_verfahren(params.specialty)}&seite={i + 1}"
            for i in range(pages)
        ]

    def _parse_list_page(self, html: str) -> list[ListEntry]:
        soup = BeautifulSoup(html, "lxml")
        entries: list[ListEntry] = []
        # Real selectors TBD; common patterns: .therapeut, .search-result, li.entry
        for block in soup.select(".therapeut, .search-result, .result, li.entry"):
            name_el = block.select_one("h2, h3, .name")
            if name_el is None:
                continue
            name = clean(name_el.get_text())
            if not name:
                continue
            address_el = block.select_one(".adresse, .address, .anschrift")
            phone_el = block.select_one(".telefon, .phone, .tel")
            entries.append(
                ListEntry(
                    name=name,
                    detail_url=extract_link(block, self.base_url),
                    address=clean(address_el.get_text()) if address_el else None,
                    telefon=clean(phone_el.get_text()) if phone_el else None,
                )
            )
        return entries

    def _parse_detail_page(self, html: str, *, fallback: ListEntry) -> TherapistData:
        soup = BeautifulSoup(html, "lxml")
        name = clean(text_of(soup, "h1, .name")) or fallback.name
        address = (
            clean(text_of(soup, ".adresse, .address, address")) or fallback.address
        )
        telefon = clean(text_of(soup, ".telefon, .phone, .tel")) or fallback.telefon
        email = extract_email_from_html(html)
        website = extract_external_website(soup, exclude_host="psych-info")
        languages = extract_list(soup, ".sprachen, .languages")
        therapieform = extract_list(soup, ".verfahren, .methoden, .therapieform")
        insurance = _extract_insurance(soup)
        return TherapistData(
            name=name,
            address=address,
            telefon=telefon,
            email=email,
            website=website,
            languages=languages,
            therapieform=therapieform,
            insurance_type=insurance,
            sources=[self.name],
        )


def _extract_insurance(soup: BeautifulSoup) -> InsuranceType | None:
    text = soup.get_text(" ", strip=True).lower()
    has_kasse = (
        "kassenzulassung" in text or "kassensitz" in text or "gesetzlich" in text
    )
    has_privat = (
        "privat" in text or "kostenerstattung" in text or "selbstzahler" in text
    )
    if has_kasse and has_privat:
        return "both"
    if has_kasse:
        return "kassen"
    if has_privat:
        return "privat"
    return None


def _verfahren(specialty: str) -> str:
    key = specialty.strip().lower()
    if "kinder" in key:
        return "KJP"
    if "psycholog" in key or "psychotherap" in key:
        return "PP"
    return ""
