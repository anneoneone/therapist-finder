"""Data models for therapist finder application."""

from typing import List, Optional
from pydantic import BaseModel, validator


class UserInfo(BaseModel):
    """User information for email generation."""
    
    name: str
    email: str  # Temporarily using str instead of EmailStr
    telefon: str
    address: str
    vermittlungscode: str
    
    @validator('name', 'telefon', 'address', 'vermittlungscode')
    def not_empty(cls, v: str) -> str:
        """Ensure fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class TherapistData(BaseModel):
    """Therapist information parsed from documents."""
    
    name: str
    address: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None
    therapieform: List[str] = []
    sprechzeiten: List[str] = []
    salutation: Optional[str] = None
    
    @validator('name')
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
    
    @validator('subject', 'body')
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
        return self.entries_with_email + self.entries_with_phone - self.entries_with_both
