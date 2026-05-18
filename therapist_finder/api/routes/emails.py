"""Email generation endpoints."""

from fastapi import APIRouter, HTTPException

from ...config import Settings
from ...email.generator import EmailGenerator
from ...email.templates import TemplateManager
from ...models import TherapistData, UserInfo
from .. import contacts_store
from ..ai.mail_generator import AiUnavailableError, generate_mail_body
from ..schemas import (
    AiGenerateRequest,
    AiGenerateResponse,
    EmailDraftResponse,
    GenerateRequest,
    GenerateResponse,
    TemplateResponse,
    TherapistResponse,
)

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("/template", response_model=TemplateResponse)
async def get_template() -> TemplateResponse:
    """Return the on-disk default email template body.

    Used by the frontend's "Mail template body" step to pre-fill the
    editor textarea so the user can tweak the body before drafts are
    generated.
    """
    try:
        settings = Settings()
        body = TemplateManager(settings).load_template()
        return TemplateResponse(body=body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load template: {str(e)}",
        ) from e


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
            f'"{(t.name or "").replace(chr(34), chr(34) + chr(34))}"',
            f'"{(t.email or "").replace(chr(34), chr(34) + chr(34))}"',
            f'"{(t.phone or "").replace(chr(34), chr(34) + chr(34))}"',
            f'"{(t.address or "").replace(chr(34), chr(34) + chr(34))}"',
        ]
        rows.append(",".join(row))

    return "\n".join(rows)


@router.post("/generate", response_model=GenerateResponse)
async def generate_emails(request: GenerateRequest) -> GenerateResponse:
    """Generate email drafts for therapists.

    Args:
        request: Therapist list and user information.

    Returns:
        Generated email drafts and CSV table.

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
                table_csv=_generate_csv(request.therapists),
            )

        # Convert to internal models
        therapist_data = [_convert_to_therapist_data(t) for t in therapists_with_email]
        user_info = _convert_to_user_info(request)

        # Generate email drafts
        drafts = generator.create_drafts(
            therapist_data, user_info, template_body=request.template_body
        )

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

        # Generate CSV table
        csv_content = _generate_csv(request.therapists)

        return GenerateResponse(
            drafts=draft_responses,
            table_csv=csv_content,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate emails: {str(e)}",
        ) from e


@router.post("/ai-generate", response_model=AiGenerateResponse)
async def ai_generate_mail_body(req: AiGenerateRequest) -> AiGenerateResponse:
    """Generate a therapist-inquiry mail body via the configured LLM.

    Looks up previously sent bodies for the requested therapist emails so
    the model can vary phrasing on re-contact. Returns the body only —
    greeting, contact info, and closing are added client-side by the
    existing language packs.
    """
    prior_map = contacts_store.get_prior_mails(req.therapist_emails)
    prior_bodies: list[str] = []
    for bodies in prior_map.values():
        prior_bodies.extend(bodies)

    try:
        body = generate_mail_body(
            target_lang=req.target_lang,
            insurance=req.insurance,
            prior_bodies=prior_bodies,
        )
    except AiUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI generation failed: {e}",
        ) from e

    return AiGenerateResponse(body=body)
