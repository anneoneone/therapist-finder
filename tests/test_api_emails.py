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
    assert body["body"].strip() != ""


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


def test_generate_without_template_body_uses_default() -> None:
    """Omitting template_body falls back to the on-disk template (no error)."""
    client = TestClient(app)
    payload = {
        "therapists": [
            {
                "name": "Dr. Frau Mustermann",
                "email": "frau.mustermann@example.com",
                "salutation": "Sehr geehrte Frau Dr. Mustermann",
            }
        ],
        "user_info": {"first_name": "Anton", "last_name": "Kress"},
    }
    resp = client.post("/api/emails/generate", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["drafts"]) == 1
    # Default template should not contain our custom marker.
    assert "XYZ123" not in data["drafts"][0]["body"]
