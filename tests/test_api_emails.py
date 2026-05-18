"""Tests for /api/emails/* endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from therapist_finder.api import contacts_store
from therapist_finder.api.ai import mail_generator
from therapist_finder.api.main import app


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "contacts.db"
    monkeypatch.setenv("THERAPIST_FINDER_CONTACTS_DB", str(db))
    contacts_store.init_db()
    yield db


def test_get_template_returns_body() -> None:
    """GET /emails/template returns the configured default body."""
    client = TestClient(app)
    resp = client.get("/api/emails/template")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "body" in body
    assert isinstance(body["body"], str)


def test_generate_uses_custom_template_body() -> None:
    """When template_body is provided, drafts are rendered from it."""
    client = TestClient(app)
    payload = {
        "therapists": [
            {
                "name": "Dr. Frau Mustermann",
                "email": "frau.mustermann@example.com",
                "salutation": "Sehr geehrte Frau Dr. Mustermann",
            }
        ],
        "user_info": {
            "first_name": "Anton",
            "last_name": "Kress",
            "email": "anton@example.com",
        },
        "template_body": "<ANREDE>,\nThis is a CUSTOM body marker XYZ123.",
    }

    resp = client.post("/api/emails/generate", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["drafts"]) == 1
    draft = data["drafts"][0]
    assert "CUSTOM body marker XYZ123" in draft["body"]
    assert "Sehr geehrte Frau Dr. Mustermann" in draft["body"]


def test_generate_substitutes_user_placeholders() -> None:
    """Curly-brace placeholders in template_body are filled from user_info."""
    client = TestClient(app)
    payload = {
        "therapists": [
            {
                "name": "Dr. Frau Mustermann",
                "email": "frau.mustermann@example.com",
                "salutation": "Sehr geehrte Frau Dr. Mustermann",
            }
        ],
        "user_info": {
            "first_name": "Anton",
            "last_name": "Kress",
            "phone": "0177 123456",
            "email": "anton@example.com",
            "vermittlungscode": "ABC-123",
        },
        "template_body": (
            "<ANREDE>,\n\nMy custom body.\n\n"
            "Meine Kontaktdaten:\n{name}\nTel.: {telefon}\n"
            "E-Mail: {email}\nVermittlungscode: {vermittlungscode}\n\n"
            "Mit besten Grüßen\n{name}"
        ),
    }
    resp = client.post("/api/emails/generate", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()["drafts"][0]["body"]
    assert "Anton Kress" in body
    assert "0177 123456" in body
    assert "anton@example.com" in body
    assert "ABC-123" in body
    assert "Sehr geehrte Frau Dr. Mustermann" in body


def test_ai_generate_returns_503_when_key_missing(
    temp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Endpoint surfaces AiUnavailableError as HTTP 503."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    client = TestClient(app)
    resp = client.post(
        "/api/emails/ai-generate",
        json={
            "target_lang": "de",
            "insurance": "gesetzlich",
            "therapist_emails": [],
            "browser_id": "anon-1",
        },
    )
    assert resp.status_code == 503, resp.text
    assert "GEMINI_API_KEY" in resp.json()["detail"]


def test_ai_generate_success_passes_prior_bodies(
    temp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prior bodies for requested therapists are forwarded to the generator."""
    contacts_store.record_sent_mail(
        "doc1@example.com", "anon-1", "Erster Anlauf bei Praxis 1.", target_lang="de"
    )
    contacts_store.record_sent_mail(
        "doc2@example.com", "anon-1", "Andere Formulierung.", target_lang="de"
    )

    captured: dict = {}

    def fake_generate(*, target_lang, insurance, prior_bodies):  # type: ignore[no-untyped-def]
        captured["target_lang"] = target_lang
        captured["insurance"] = insurance
        captured["prior_bodies"] = list(prior_bodies)
        return "Stub-generated body."

    monkeypatch.setattr(
        "therapist_finder.api.routes.emails.generate_mail_body", fake_generate
    )

    client = TestClient(app)
    resp = client.post(
        "/api/emails/ai-generate",
        json={
            "target_lang": "de",
            "insurance": "privat",
            "therapist_emails": ["DOC1@example.com", "doc2@example.com"],
            "browser_id": "anon-1",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"body": "Stub-generated body."}
    assert captured["target_lang"] == "de"
    assert captured["insurance"] == "privat"
    # Both prior bodies (one per therapist) were forwarded.
    assert "Erster Anlauf bei Praxis 1." in captured["prior_bodies"]
    assert "Andere Formulierung." in captured["prior_bodies"]


def test_ai_generate_empty_emails_passes_no_prior_bodies(
    temp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def fake_generate(*, target_lang, insurance, prior_bodies):  # type: ignore[no-untyped-def]
        captured["prior_bodies"] = list(prior_bodies)
        return "ok"

    monkeypatch.setattr(
        "therapist_finder.api.routes.emails.generate_mail_body", fake_generate
    )

    client = TestClient(app)
    resp = client.post(
        "/api/emails/ai-generate",
        json={
            "target_lang": "en",
            "insurance": None,
            "therapist_emails": [],
            "browser_id": "anon-1",
        },
    )
    assert resp.status_code == 200
    assert captured["prior_bodies"] == []


def test_strip_boilerplate_removes_greeting_and_closing() -> None:
    raw = (
        "Sehr geehrte Frau Dr. Müller,\n\n"
        "ich suche aktuell einen Therapieplatz und würde mich über eine "
        "Rückmeldung freuen.\n\n"
        "Mit freundlichen Grüßen\nAnton"
    )
    cleaned = mail_generator._strip_boilerplate(raw)
    assert "Sehr geehrte" not in cleaned
    assert "Mit freundlichen" not in cleaned
    assert "Anton" not in cleaned
    assert "Therapieplatz" in cleaned
