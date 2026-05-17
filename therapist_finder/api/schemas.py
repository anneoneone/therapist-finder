"""API request and response schemas."""

from pydantic import BaseModel, Field, HttpUrl


class UserInfoRequest(BaseModel):
    """User information for email generation."""

    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    birth_date: str | None = Field(None, description="Birth date (DD.MM.YYYY)")
    insurance: str | None = Field(None, description="Health insurance name")
    email: str | None = Field(None, description="User's email address")
    phone: str | None = Field(None, description="User's phone number")
    vermittlungscode: str | None = Field(None, description="Referral code")

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"


class TherapistResponse(BaseModel):
    """Therapist data in API response."""

    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    salutation: str | None = None
    specialty: str | None = None
    specialty_label: str | None = None
    distance_km: float | None = None
    sources: list[str] = []


class ParseResponse(BaseModel):
    """Response from parse endpoint."""

    therapists: list[TherapistResponse]
    total: int
    with_email: int


class ParseUrlRequest(BaseModel):
    """Request to fetch and parse a PDF from a remote URL."""

    url: HttpUrl = Field(
        ...,
        description="HTTPS URL pointing to a PDF hosted on psych-info.de",
    )


class SpecialtyOption(BaseModel):
    """A selectable specialty for the search UI dropdown."""

    key: str
    label: str


class SpecialtiesResponse(BaseModel):
    """List of selectable specialties, in display order."""

    specialties: list[SpecialtyOption]
    default: str


class EmailDraftResponse(BaseModel):
    """Email draft in API response."""

    to: str
    subject: str
    body: str
    therapist_name: str


class GenerateRequest(BaseModel):
    """Request for email generation."""

    therapists: list[TherapistResponse]
    user_info: UserInfoRequest
    template_body: str | None = Field(
        None,
        description=(
            "Optional template body override. If unset, the server-side "
            "default template is loaded from disk."
        ),
    )


class GenerateResponse(BaseModel):
    """Response from generate endpoint."""

    drafts: list[EmailDraftResponse]
    table_csv: str


class TemplateResponse(BaseModel):
    """Response from GET /emails/template."""

    body: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    code: str | None = None
