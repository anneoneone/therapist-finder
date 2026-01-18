"""Data models for therapist finder application."""

from pydantic import BaseModel, field_validator


class UserInfo(BaseModel):
    """User information for email generation."""

    name: str
    email: str = ""  # Optional email
    telefon: str = ""  # Optional phone
    address: str = ""  # Optional address
    vermittlungscode: str = ""  # Optional referral code

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Ensure name is not empty."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class TherapistData(BaseModel):
    """Therapist information parsed from documents."""

    name: str
    address: str | None = None
    telefon: str | None = None
    email: str | None = None
    therapieform: list[str] = []
    sprechzeiten: list[str] = []
    salutation: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Ensure name is not empty."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @property
    def has_contact_info(self) -> bool:
        """Check if therapist has any contact information."""
        return bool(self.email or self.telefon)

    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        return self.address or "No address provided"


class EmailDraft(BaseModel):
    """Email draft for contacting therapists."""

    to: str
    subject: str
    body: str
    therapist_name: str

    @field_validator("subject", "body")
    @classmethod
    def not_empty(cls, v: str) -> str:
        """Ensure fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class ParsingStatistics(BaseModel):
    """Statistics from parsing operation."""

    total_entries: int
    entries_with_email: int
    entries_with_phone: int
    entries_with_both: int

    @property
    def entries_without_email(self) -> int:
        """Number of entries without email."""
        return self.total_entries - self.entries_with_email

    @property
    def entries_without_phone(self) -> int:
        """Number of entries without phone."""
        return self.total_entries - self.entries_with_phone

    @property
    def contactable_entries(self) -> int:
        """Number of entries with at least one contact method."""
        return (
            self.entries_with_email + self.entries_with_phone - self.entries_with_both
        )
