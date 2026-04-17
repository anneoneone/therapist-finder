"""Therapist parsing + address-search endpoints."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, UploadFile

from ...config import Settings
from ...models import TherapistData
from ...parsers.arztsuche_api import Arztsuche116117Source
from ...parsers.pdf_parser import PDFParser
from ...parsers.text_parser import TextParser
from ...sources.base import SearchParams
from ...sources.geocode import Geocoder, GeocodingError
from ...sources.merger import merge_and_rank
from ...sources.overpass import OverpassSource
from ...sources.psych_info import PsychInfoSource
from ...sources.therapie_de import TherapieDeSource
from ..schemas import (
    ParseResponse,
    SearchByAddressRequest,
    SearchByAddressResponse,
    TherapistResponse,
)

router = APIRouter(prefix="/therapists", tags=["therapists"])


def _build_source(name: str, settings: Settings) -> object | None:
    """Instantiate a source by name. Returns None for unknown names."""
    if name == "116117":
        return Arztsuche116117Source()
    if name == "osm":
        return OverpassSource(
            endpoint=settings.overpass_endpoint,
            user_agent=settings.scraper_user_agent,
        )
    if name == "psych_info":
        return PsychInfoSource(
            user_agent=settings.scraper_user_agent,
            min_delay_seconds=settings.scraper_min_delay_seconds,
        )
    if name == "therapie_de":
        return TherapieDeSource(
            user_agent=settings.scraper_user_agent,
            min_delay_seconds=max(settings.scraper_min_delay_seconds, 3.0),
        )
    return None


def _therapist_to_response(t: TherapistData) -> TherapistResponse:
    return TherapistResponse(
        name=t.name,
        address=t.address,
        phone=t.telefon,
        email=t.email,
        salutation=t.salutation,
        distance_km=t.distance_km,
        sources=list(t.sources),
    )


@router.post("/search-by-address", response_model=SearchByAddressResponse)
async def search_by_address(
    request: SearchByAddressRequest,
) -> SearchByAddressResponse:
    """Return the N closest providers to a street address.

    Geocodes the input address, queries every enabled source in parallel,
    merges duplicates across sources, and ranks by haversine distance.
    """
    settings = Settings()
    requested = request.sources or settings.enabled_sources

    geocoder = Geocoder(
        endpoint=settings.nominatim_endpoint,
        user_agent=settings.scraper_user_agent,
        cache_dir=settings.http_cache_dir,
    )
    try:
        origin = geocoder.geocode(request.address)
    except GeocodingError as e:
        geocoder.close()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        geocoder.close()
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {e}") from e

    params = SearchParams(
        specialty=request.specialty,
        lat=origin.lat,
        lon=origin.lon,
        radius_km=request.radius_km,
        limit_per_source=max(request.max_results * 3, 50),
    )

    sources = [s for s in (_build_source(n, settings) for n in requested) if s]
    if not sources:
        geocoder.close()
        raise HTTPException(status_code=400, detail="No valid sources selected")

    results: dict[str, list[TherapistData]] = {}
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = {
            pool.submit(src.search, params): src.name  # type: ignore[attr-defined]
            for src in sources
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception:  # noqa: BLE001
                results[name] = []

    for src in sources:
        src.close()  # type: ignore[attr-defined]

    merged = merge_and_rank(
        results,
        origin.lat,
        origin.lon,
        request.max_results,
        geocoder=geocoder,
    )
    geocoder.close()

    responses = [_therapist_to_response(t) for t in merged]
    with_email = sum(1 for t in merged if t.email)
    return SearchByAddressResponse(
        therapists=responses,
        total=len(responses),
        with_email=with_email,
        origin_address=origin.display_name,
        origin_lat=origin.lat,
        origin_lon=origin.lon,
    )


@router.post("/parse", response_model=ParseResponse)
async def parse_file(
    file: UploadFile = File(..., description="PDF or text file to parse"),
) -> ParseResponse:
    """Parse therapist data from uploaded PDF or text file.

    Args:
        file: Uploaded file (PDF or plain text).

    Returns:
        Parsed therapist data with statistics.

    Raises:
        HTTPException: If file type is unsupported or parsing fails.
    """
    # Validate file type
    filename = file.filename or ""
    is_pdf = filename.lower().endswith(".pdf") or file.content_type == "application/pdf"
    is_text = (
        filename.lower().endswith(".txt")
        or file.content_type == "text/plain"
        or file.content_type == "application/octet-stream"
    )

    if not (is_pdf or is_text):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use PDF or TXT files.",
        )

    # Save to temp file for processing
    suffix = ".pdf" if is_pdf else ".txt"
    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        # Parse file
        settings = Settings()
        parser = PDFParser(settings) if is_pdf else TextParser(settings)
        therapists = parser.parse_file(tmp_path)

        # Convert to response format
        therapist_responses = [_therapist_to_response(t) for t in therapists]

        with_email = sum(1 for t in therapists if t.email)

        return ParseResponse(
            therapists=therapist_responses,
            total=len(therapists),
            with_email=with_email,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse file: {str(e)}",
        ) from e

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()
