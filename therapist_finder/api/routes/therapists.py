"""Therapist parsing endpoints."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from fastapi import APIRouter, File, HTTPException, UploadFile
import httpx

from ...config import Settings
from ...models import TherapistData
from ...parsers.pdf_parser import PDFParser
from ...parsers.text_parser import TextParser
from ...sources import specialties
from ..schemas import (
    ParseResponse,
    ParseUrlRequest,
    SpecialtiesResponse,
    SpecialtyOption,
    TherapistResponse,
)

router = APIRouter(prefix="/therapists", tags=["therapists"])

_ALLOWED_PARSE_URL_HOSTS = {"psych-info.de", "www.psych-info.de"}


def _therapist_to_response(t: TherapistData) -> TherapistResponse:
    key = t.specialty or specialties.infer_key(t)
    label = (
        specialties.SPECIALTIES[key].label if key in specialties.SPECIALTIES else None
    )
    return TherapistResponse(
        name=t.name,
        address=t.address,
        phone=t.telefon,
        email=t.email,
        salutation=t.salutation,
        specialty=key,
        specialty_label=label,
        distance_km=t.distance_km,
        sources=list(t.sources),
    )


@router.get("/specialties", response_model=SpecialtiesResponse)
async def list_specialties() -> SpecialtiesResponse:
    """Return the specialties offered in the search dropdown."""
    return SpecialtiesResponse(
        specialties=[
            SpecialtyOption(key=s.key, label=s.label)
            for s in specialties.all_specialties()
        ],
        default=specialties.DEFAULT_KEY,
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


@router.post("/parse-url", response_model=ParseResponse)
async def parse_url(request: ParseUrlRequest) -> ParseResponse:
    """Download a PDF from a psych-info.de URL and parse it.

    The host allowlist is narrow on purpose — the parser only understands
    Psych-Info Resultate PDFs for now. Loosen the allowlist once we support
    more remote layouts.
    """
    parsed = urlparse(str(request.url))
    if parsed.scheme != "https":
        raise HTTPException(
            status_code=400,
            detail="URL must use https://",
        )
    if (parsed.hostname or "").lower() not in _ALLOWED_PARSE_URL_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Only psych-info.de URLs are accepted",
        )

    tmp_path: Path | None = None
    try:
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(str(request.url))
                response.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to download PDF: {e}",
            ) from e

        content_type = response.headers.get("content-type", "").lower()
        url_path = parsed.path.lower()
        looks_like_pdf = content_type.startswith(
            "application/pdf"
        ) or url_path.endswith(".pdf")
        if not looks_like_pdf:
            raise HTTPException(
                status_code=502,
                detail=f"Upstream did not return a PDF (content-type={content_type!r})",
            )

        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)

        try:
            therapists = PDFParser(Settings()).parse_file(tmp_path)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail=f"Failed to parse PDF: {e}",
            ) from e

        therapist_responses = [_therapist_to_response(t) for t in therapists]
        with_email = sum(1 for t in therapists if t.email)
        return ParseResponse(
            therapists=therapist_responses,
            total=len(therapists),
            with_email=with_email,
        )
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
