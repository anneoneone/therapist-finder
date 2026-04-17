# Data Sources for Berlin Healthcare Providers

The `crawl-berlin` command aggregates providers from several public Berlin
directories. Given a street address, it geocodes it, queries each enabled
source within a radius, merges duplicates across sources, and returns the
**N closest providers** ranked by haversine distance.

## Usage

```bash
poetry run therapist-finder crawl-berlin \
  --address "Kastanienallee 12, 10435 Berlin" \
  --max 20 \
  --specialty "Psychotherapeut" \
  --radius 15 \
  --sources 116117,osm,ptk,aeka \
  --output clients/anna/
```

Output files (when `--output` is given):

- `therapists_nearest.json` — full merged records, sorted by `distance_km`.
- `therapists_nearest.md` — Markdown table preview.

## Sources

| Name     | Directory                                        | Coverage                          | Legal                 |
|----------|--------------------------------------------------|-----------------------------------|-----------------------|
| `116117` | KBV Arztsuche (`arztsuche.116117.de`)            | KV-accredited (Kassensitz)        | Public API            |
| `osm`    | OpenStreetMap Overpass API                       | Crowdsourced, incl. private       | ODbL                  |
| `ptk`    | Psychotherapeutenkammer Berlin register          | All licensed Psychotherapists     | Public statutory reg. |
| `aeka`   | Ärztekammer Berlin (`arztauskunft-berlin.de`)    | MDs incl. psychiatrists           | Public statutory reg. |

Commercial directories (Jameda, Doctolib, Therapie.de) are intentionally
excluded: their ToS explicitly prohibit automated extraction.

## Behaviour

- Each source is queried in parallel with a 2 s per-host delay for scrapers.
- HTML scrapers honour `robots.txt` by default.
- Geocoding uses Nominatim with an identifying User-Agent and 1 rps rate limit.
  Responses are cached to `.cache/therapist-finder/` to avoid re-hitting
  Nominatim during development.
- Deduplication matches by normalised last name + postcode + house number,
  falling back to email. Merged records union their non-null fields and record
  all contributing sources in `sources`.

## Finding hidden JSON APIs (recon)

The PTK Berlin and Ärztekammer Berlin scrapers use best-effort CSS selectors
because their HTML isn't publicly documented. Before hardening them, run the
recon script to see whether the sites are really SPAs backed by a JSON API
(like `arztsuche.116117.de`) — if they are, replace the HTML scraper with a
JSON client for much better reliability.

### Running the recon

```bash
poetry install --with dev
poetry run playwright install chromium
poetry run python scripts/recon_sources.py
```

Optional flags:

```bash
# Only probe specific targets
poetry run python scripts/recon_sources.py --only ptk_berlin,psych_info

# Add an extra target on the fly
poetry run python scripts/recon_sources.py \
    --extra kbv=https://arztsuche.kbv.de/
```

The script launches headless Chromium, loads each target, enumerates its
forms / scripts / iframes, submits a `"Berlin"` search, and captures every
XHR/fetch call the page makes. Output lands in `recon/`:

- `recon/summary.md` — human-readable overview of each site.
- `recon/<site>.json` — full capture (request + response headers, bodies,
  discovery JSON, first 20 KB of the final HTML snapshot).

Look at `recon/summary.md` first — if a site lists clean `GET /api/...` or
`POST /search` calls returning `application/json`, that's your API. Replace
the HTML-scraping `TherapistSource` with an httpx client that posts the same
payload; reuse the structure of `therapist_finder/parsers/arztsuche_api.py`.

### Default targets

| name          | URL                                                                           |
|---------------|-------------------------------------------------------------------------------|
| `ptk_berlin`  | `https://www.psychotherapeutenkammer-berlin.de/psychotherapeutensuche`        |
| `psych_info`  | `https://www.psych-info.de/psychotherapeutensuche/` (used by many Landeskammern) |
| `aeka_berlin` | `https://www.arztauskunft-berlin.de/`                                         |
| `kv_berlin`   | `https://www.kvberlin.de/fuer-patienten/arzt-und-psychotherapeutensuche`      |

Psych-Info powers the therapist search for several German Landeskammern, so
if it exposes a JSON API, a single integration replaces `ptk_berlin` and
extends coverage beyond Berlin.

## Configuration

Override via environment variables (prefix `THERAPIST_FINDER_`) or `.env`:

```
THERAPIST_FINDER_ENABLED_SOURCES=["116117","osm","ptk","aeka"]
THERAPIST_FINDER_SCRAPER_USER_AGENT=my-org-therapist-finder/0.2 (+https://...)
THERAPIST_FINDER_SCRAPER_MIN_DELAY_SECONDS=2.0
THERAPIST_FINDER_OVERPASS_ENDPOINT=https://overpass-api.de/api/interpreter
THERAPIST_FINDER_NOMINATIM_ENDPOINT=https://nominatim.openstreetmap.org/search
THERAPIST_FINDER_HTTP_CACHE_DIR=.cache/therapist-finder
```
