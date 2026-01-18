"""Email generation endpoints."""

from fastapi import APIRouter, HTTPException

from ...config import Settings
from ...models import EmailDraft, TherapistData, UserInfo
from ...email.generator import EmailGenerator
from ...utils.applescript_generator import create_applescript_content
from ..schemas import (
    EmailDraftResponse,
    GenerateRequest,
    GenerateResponse,
    TherapistResponse,
)

router = APIRouter(prefix="/emails", tags=["emails"])


def _convert_to_therapist_data(therapist: TherapistResponse) -> TherapistData:
    """Convert API response model to internal TherapistData."""
    return TherapistData(
        name=therapist.name,
        address=therapist.address,
        telefon=therapist.phone,
        email=therapist.email,
        salutation=therapist.salutation,
    )


def _convert_to_user_info(request: GenerateRequest) -> UserInfo:
    """Convert API request to internal UserInfo model."""
    user = request.user_info
    return UserInfo(
        name=user.full_name,
        email=user.email or "",
        telefon=user.phone or "",
        address="",  # Not collected in frontend
        vermittlungscode=user.vermittlungscode or "",
    )


def _generate_csv(therapists: list[TherapistResponse]) -> str:
    """Generate CSV content from therapist list."""
    headers = ["Name", "Email", "Phone", "Address"]
    rows = [",".join(headers)]

    for t in therapists:
        row = [
            f'"{(t.name or "").replace(chr(34), chr(34)+chr(34))}"',
            f'"{(t.email or "").replace(chr(34), chr(34)+chr(34))}"',
            f'"{(t.phone or "").replace(chr(34), chr(34)+chr(34))}"',
            f'"{(t.address or "").replace(chr(34), chr(34)+chr(34))}"',
        ]
        rows.append(",".join(row))

    return "\n".join(rows)


@router.post("/generate", response_model=GenerateResponse)
async def generate_emails(request: GenerateRequest) -> GenerateResponse:
    """Generate email drafts and AppleScript for therapists.

    Args:
        request: Therapist list and user information.

    Returns:
        Generated email drafts, AppleScript content, and CSV table.

    Raises:
        HTTPException: If generation fails.
    """
    try:
        settings = Settings()
        generator = EmailGenerator(settings)

        # Filter therapists with email
        therapists_with_email = [t for t in request.therapists if t.email]

        if not therapists_with_email:
            return GenerateResponse(
                drafts=[],
                applescript="",
                table_csv=_generate_csv(request.therapists),
            )

        # Convert to internal models
        therapist_data = [_convert_to_therapist_data(t) for t in therapists_with_email]
        user_info = _convert_to_user_info(request)

        # Generate email drafts
        drafts = generator.create_drafts(therapist_data, user_info)

        # Convert drafts to response format
        draft_responses = [
            EmailDraftResponse(
                to=d.to,
                subject=d.subject,
                body=d.body,
                therapist_name=d.therapist_name,
            )
            for d in drafts
        ]

        # Generate AppleScript
        applescript = create_applescript_content(drafts)

        # Generate CSV table
        csv_content = _generate_csv(request.therapists)

        return GenerateResponse(
            drafts=draft_responses,
            applescript=applescript,
            table_csv=csv_content,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate emails: {str(e)}",
        ) from e
