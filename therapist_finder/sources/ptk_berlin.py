"""Scraper for the Psychotherapeutenkammer Berlin public register.

Respects robots.txt, uses an identifying User-Agent, and waits the configured
minimum delay between requests to keep the server load low.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import httpx

from therapist_finder.models import InsuranceType, TherapistData
from therapist_finder.sources.base import SearchParams, TherapistSource
from therapist_finder.sources.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://psychotherapeutenkammer-berlin.de"
_SEARCH_PATH = "/psychotherapeutensuche"


class PTKBerlinSource(TherapistSource):
    """HTML scraper for the PTK Berlin Psychotherapeutensuche."""

    name = "ptk"

    def __init__(
        self,
        user_agent: str,
        base_url: str = _DEFAULT_BASE,
        search_path: str = _SEARCH_PATH,
        min_delay_seconds: float = 2.0,
        client: httpx.Client | None = None,
        respect_robots_txt: bool = True,
    ) -> None:
        """Initialise the PTK Berlin scraper."""
        self._base_url = base_url.rstrip("/")
        self._search_url = urljoin(self._base_url + "/", search_path.lstrip("/"))
        self._user_agent = user_agent
        self._client = client or httpx.Client(
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self._owns_client = client is None
        self._rate_limiter = RateLimiter(min_delay_seconds=min_delay_seconds)
        self._respect_robots = respect_robots_txt
        self._robots: RobotFileParser | None = None

    def search(self, params: SearchParams) -> list[TherapistData]:
        """Return PTK Berlin entries matching the specialty/location filter.

        The Kammer search form does not accept lat/lon; we paginate all
        Berlin results for the requested specialty and let the merger rank
        them by distance from the geocoded origin.
        """
        if not self._allowed(self._search_url):
            logger.warning("robots.txt disallows %s; skipping PTK Berlin", self._search_url)
            return []

        results: list[TherapistData] = []
        for page_url in self._iter_result_pages(params):
            list_html = self._fetch(page_url)
            if list_html is None:
                continue
            entries = _parse_list_page(list_html, self._base_url)
            if not entries:
                break
            for entry in entries:
                detail_html = self._fetch(entry.detail_url) if entry.detail_url else None
                if detail_html is not None:
                    results.append(
                        _parse_detail_page(detail_html, fallback=entry, source=self.name)
                    )
                else:
                    results.append(entry.to_therapist(self.name))
        logger.info("PTK Berlin returned %d providers", len(results))
        return results

    def close(self) -> None:
        """Close HTTP client if owned."""
        if self._owns_client:
            self._client.close()

    def _iter_result_pages(self, params: SearchParams) -> list[str]:
        # PTK search uses query params like ?ort=Berlin&verfahren=...
        # We fetch up to ``limit_per_source / 20`` pages (approx 20 per page).
        base = self._search_url
        pages = max(1, (params.limit_per_source + 19) // 20)
        return [
            f"{base}?ort=Berlin&seite={i + 1}&verfahren={_specialty_param(params.specialty)}"
            for i in range(pages)
        ]

    def _fetch(self, url: str) -> str | None:
        if not self._allowed(url):
            return None
        self._rate_limiter.wait(_host(url))
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("PTK fetch failed for %s: %s", url, e)
            return None
        return resp.text

    def _allowed(self, url: str) -> bool:
        if not self._respect_robots:
            return True
        if self._robots is None:
            self._robots = RobotFileParser()
            robots_url = urljoin(self._base_url + "/", "robots.txt")
            self._rate_limiter.wait(_host(robots_url))
            try:
                resp = self._client.get(robots_url)
                if resp.status_code == 200:
                    self._robots.parse(resp.text.splitlines())
                else:
                    # Permissive fallback: no robots.txt published
                    self._robots.parse([])
            except httpx.HTTPError:
                self._robots.parse([])
        return self._robots.can_fetch(self._user_agent, url)


class _ListEntry:
    """Partial data from a search-result list page."""

    def __init__(
        self,
        name: str,
        detail_url: str | None,
        address: str | None,
        telefon: str | None,
    ) -> None:
        """Initialise a list entry."""
        self.name = name
        self.detail_url = detail_url
        self.address = address
        self.telefon = telefon

    def to_therapist(self, source: str) -> TherapistData:
        """Convert to a :class:`TherapistData` record with just list data."""
        return TherapistData(
            name=self.name,
            address=self.address,
            telefon=self.telefon,
            sources=[source],
        )


def _parse_list_page(html: str, base_url: str) -> list[_ListEntry]:
    soup = BeautifulSoup(html, "lxml")
    entries: list[_ListEntry] = []
    # The Kammer list uses ``<div class="result">`` blocks (best-effort
    # selectors; adjust when HTML changes).
    for block in soup.select(".result, .therapeut-eintrag, li.entry"):
        name_el = block.select_one("h2, h3, .name")
        if name_el is None:
            continue
        name = _clean(name_el.get_text())
        if not name:
            continue
        detail_url = _extract_link(block, base_url)
        address_el = block.select_one(".adresse, .address")
        address = _clean(address_el.get_text()) if address_el else None
        phone_el = block.select_one(".telefon, .phone")
        telefon = _clean(phone_el.get_text()) if phone_el else None
        entries.append(
            _ListEntry(
                name=name,
                detail_url=detail_url,
                address=address,
                telefon=telefon,
            )
        )
    return entries


def _parse_detail_page(
    html: str, *, fallback: _ListEntry, source: str
) -> TherapistData:
    soup = BeautifulSoup(html, "lxml")
    name = _clean(_text(soup, "h1, .name")) or fallback.name
    address = _clean(_text(soup, ".adresse, address, .address")) or fallback.address
    telefon = _clean(_text(soup, ".telefon, .phone")) or fallback.telefon
    email = _extract_email(html)
    website = _extract_website(soup)
    languages = _extract_list(soup, ".sprachen, .languages")
    therapieform = _extract_list(soup, ".verfahren, .methoden, .therapieform")
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
        sources=[source],
    )


def _text(soup: BeautifulSoup, selectors: str) -> str:
    el = soup.select_one(selectors)
    return el.get_text(" ", strip=True) if el else ""


def _extract_list(soup: BeautifulSoup, selectors: str) -> list[str]:
    text = _text(soup, selectors)
    return [p.strip() for p in re.split(r"[,;/]", text) if p.strip()]


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _extract_email(html: str) -> str | None:
    m = _EMAIL_RE.search(html)
    return m.group(0) if m else None


def _extract_website(soup: BeautifulSoup) -> str | None:
    for a in soup.select("a[href^='http']"):
        href = a.get("href")
        if (
            isinstance(href, str)
            and "mailto:" not in href
            and "psychotherapeutenkammer" not in href
        ):
            return href
    return None


def _extract_insurance(soup: BeautifulSoup) -> InsuranceType | None:
    text = soup.get_text(" ", strip=True).lower()
    has_kasse = "kassenzulassung" in text or "gesetzlich" in text
    has_privat = "privat" in text
    if has_kasse and has_privat:
        return "both"
    if has_kasse:
        return "kassen"
    if has_privat:
        return "privat"
    return None


def _extract_link(block: object, base_url: str) -> str | None:
    """Return the absolute URL of the first ``<a href>`` inside ``block``."""
    # ``block`` is a bs4 Tag; typed as ``object`` to keep imports minimal.
    find = getattr(block, "find", None)
    if find is None:
        return None
    link_el = find("a", href=True)
    if link_el is None:
        return None
    href = link_el.get("href")
    if not isinstance(href, str):
        return None
    return urljoin(base_url + "/", href)


def _specialty_param(specialty: str) -> str:
    key = specialty.strip().lower()
    if "kinder" in key:
        return "KJP"
    if "psychologisch" in key or "psychotherap" in key:
        return "PP"
    return ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc
