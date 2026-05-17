"""Contact-log endpoints: record sent emails and query global counts."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .. import contacts_store

router = APIRouter(prefix="/contacts", tags=["contacts"])


class RecordContactRequest(BaseModel):
    """Payload for POST /api/contacts."""

    email: str = Field(..., description="Therapist email that was contacted")
    browser_id: str = Field(..., description="Anonymous per-browser identifier")


class RecordContactResponse(BaseModel):
    """Result of POST /api/contacts."""

    recorded: bool = Field(..., description="True if a new row was inserted")


class CountsRequest(BaseModel):
    """Payload for POST /api/contacts/counts."""

    emails: list[str] = Field(
        default_factory=list,
        description="Emails to look up; case-insensitive",
    )


class CountsResponse(BaseModel):
    """Global contact count per email; missing keys default to 0."""

    counts: dict[str, int]


class MineResponse(BaseModel):
    """Emails this browser has already contacted."""

    emails: list[str]


@router.post("", response_model=RecordContactResponse)
async def record(req: RecordContactRequest) -> RecordContactResponse:
    """Record a contact event. Idempotent per ``(email, browser_id)``."""
    inserted = contacts_store.record_contact(req.email, req.browser_id)
    return RecordContactResponse(recorded=inserted)


@router.post("/counts", response_model=CountsResponse)
async def counts(req: CountsRequest) -> CountsResponse:
    """Return global contact count per email. Missing keys default to 0."""
    return CountsResponse(counts=contacts_store.get_counts(req.emails))


@router.get("/mine", response_model=MineResponse)
async def mine(browser_id: str = Query(..., min_length=1)) -> MineResponse:
    """Return emails this browser has already contacted."""
    return MineResponse(emails=contacts_store.get_user_contacts(browser_id))
