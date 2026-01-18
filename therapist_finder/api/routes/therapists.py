"""Therapist parsing endpoints."""

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, UploadFile

from ...config import Settings
from ...parsers.pdf_parser import PDFParser
from ...parsers.text_parser import TextParser
from ..schemas import ParseResponse, TherapistResponse

router = APIRouter(prefix="/therapists", tags=["therapists"])


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
        therapist_responses = [
            TherapistResponse(
                name=t.name,
                address=t.address,
                phone=t.telefon,
                email=t.email,
                salutation=t.salutation,
            )
            for t in therapists
        ]

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
