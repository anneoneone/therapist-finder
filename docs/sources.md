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
