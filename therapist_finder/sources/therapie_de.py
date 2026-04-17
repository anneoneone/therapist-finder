"""Scraper for therapie.de Berlin psychotherapist listings.

URL pattern (verified public pagination):

    https://www.therapie.de/psychotherapie/-ort-/berlin/-seite-/N/

Covers ~2,700 Berlin entries including Heilpraktiker (HP-Psychotherapie) that
the statutory chambers do not list. Commercial site — AGB prohibits bulk
extraction and §87b UrhG (German database right) protects wesentliche Teile.

**Scrape politely:** residential IP only, low request rate (≥3 s/request), copy
only the fields we display, never republish the raw corpus.
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

_DEFAULT_BASE = "https://www.therapie.de"
_BERLIN_PATH = "/psychotherapie/-ort-/berlin"


class TherapieDeSource(HTMLScraper):
    """HTML scraper for therapie.de (residential IP required, polite rate)."""

    name = "therapie_de"

    def __init__(
        self,
        user_agent: str,
        base_url: str = _DEFAULT_BASE,
        listing_path: str = _BERLIN_PATH,
        min_delay_seconds: float = 3.0,
        client: object | None = None,
        respect_robots_txt: bool = True,
    ) -> None:
        """Initialise. ``listing_path`` is the Berlin listing slug."""
        super().__init__(
            user_agent=user_agent,
            base_url=base_url,
            min_delay_seconds=min_delay_seconds,
            client=client,  # type: ignore[arg-type]
            respect_robots_txt=respect_robots_txt,
        )
        self._listing_path = listing_path.strip("/")

    def _iter_list_urls(self, params: SearchParams) -> list[str]:
        # therapie.de paginates as /-seite-/N/ after the listing path.
        pages = max(1, (params.limit_per_source + 19) // 20)
        urls = [f"{self.base_url}/{self._listing_path}/"]
        urls.extend(
            f"{self.base_url}/{self._listing_path}/-seite-/{i + 1}/"
            for i in range(1, pages)
        )
        return urls

    def _parse_list_page(self, html: str) -> list[ListEntry]:
        soup = BeautifulSoup(html, "lxml")
        entries: list[ListEntry] = []
        # therapie.de result cards commonly use `.treffer`, `.ergebnis`, `.item`
        for block in soup.select(
            ".treffer, .ergebnis, .therapeutenCard, .therapeut, li.item"
        ):
            name_el = block.select_one("h2, h3, .name, .therapeutName")
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

    def _parse_detail_page(
        self, html: str, *, fallback: ListEntry
    ) -> TherapistData:
        soup = BeautifulSoup(html, "lxml")
        name = clean(text_of(soup, "h1, .name, .therapeutName")) or fallback.name
        address = clean(text_of(soup, ".adresse, .address, address")) or fallback.address
        telefon = clean(text_of(soup, ".telefon, .phone, .tel")) or fallback.telefon
        email = extract_email_from_html(html)
        website = extract_external_website(soup, exclude_host="therapie.de")
        languages = extract_list(soup, ".sprachen, .languages")
        therapieform = extract_list(
            soup, ".verfahren, .methoden, .therapieform, .schwerpunkt"
        )
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
    is_heilpraktiker = "heilpraktiker" in text
    has_kasse = "kassenzulassung" in text or "kassensitz" in text or "gesetzlich" in text
    has_privat = (
        "privat" in text or "kostenerstattung" in text or "selbstzahler" in text
    )
    if is_heilpraktiker and not has_kasse:
        return "heilpraktiker"
    if has_kasse and has_privat:
        return "both"
    if has_kasse:
        return "kassen"
    if has_privat:
        return "privat"
    return None
