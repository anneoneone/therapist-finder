"""API request and response schemas."""

from pydantic import BaseModel, Field


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
    distance_km: float | None = None
    sources: list[str] = []


class ParseResponse(BaseModel):
    """Response from parse endpoint."""

    therapists: list[TherapistResponse]
    total: int
    with_email: int


class SearchByAddressRequest(BaseModel):
    """Search by address: the webapp's default entry point."""

    address: str = Field(
        ...,
        description=(
            "Street address to search around, e.g. 'Kastanienallee 12, 10435 Berlin'"
        ),
    )
    max_results: int = Field(
        20, ge=1, le=100, description="Return the N closest providers"
    )
    specialty: str = Field("Psychotherapeut", description="Specialty filter")
    radius_km: float = Field(
        15.0, ge=0.5, le=50.0, description="Per-source search radius"
    )
    sources: list[str] | None = Field(
        None,
        description=(
            "Source names to query. Defaults to the CI-safe set configured "
            "in Settings.enabled_sources when omitted."
        ),
    )


class SearchByAddressResponse(BaseModel):
    """Response to a search-by-address request."""

    therapists: list[TherapistResponse]
    total: int
    with_email: int
    origin_address: str
    origin_lat: float
    origin_lon: float


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


class GenerateResponse(BaseModel):
    """Response from generate endpoint."""

    drafts: list[EmailDraftResponse]
    table_csv: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    code: str | None = None
