"""Tests for /api/emails/* endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from therapist_finder.api.main import app


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
