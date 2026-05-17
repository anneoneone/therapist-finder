"""Tests for the /api/therapists/parse-url endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from therapist_finder.api.main import app

PSYCH_INFO_PDF = Path(__file__).parent / "fixtures" / "psych_info_resultate_sample.pdf"


def _fake_pdf_response(
    content: bytes, *, content_type: str = "application/pdf"
) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.headers = {"content-type": content_type}
    resp.raise_for_status = MagicMock()
    return resp


def test_parse_url_happy_path() -> None:
    """Downloads bytes from psych-info.de and returns parsed therapists."""
    pdf_bytes = PSYCH_INFO_PDF.read_bytes()

    client_mock = MagicMock()
    client_mock.__enter__ = MagicMock(return_value=client_mock)
    client_mock.__exit__ = MagicMock(return_value=False)
    client_mock.get = MagicMock(return_value=_fake_pdf_response(pdf_bytes))

    client = TestClient(app)
    with patch(
        "therapist_finder.api.routes.therapists.httpx.Client", return_value=client_mock
    ):
        resp = client.post(
            "/api/therapists/parse-url",
            json={
                "url": "https://psych-info.de/wp-content/uploads/pdf/"
                "psych-info_resultate_6a0a1fd11c22f.pdf"
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] > 10
    assert body["with_email"] > 0
    first = body["therapists"][0]
    assert first["name"]
    assert first["sources"] == ["psych_info"]


def test_parse_url_rejects_non_https() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/therapists/parse-url",
        json={"url": "http://psych-info.de/foo.pdf"},
    )
    assert resp.status_code == 400
    assert "https" in resp.json()["detail"].lower()


def test_parse_url_rejects_other_host() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/therapists/parse-url",
        json={"url": "https://example.com/foo.pdf"},
    )
    assert resp.status_code == 400
    assert "psych-info.de" in resp.json()["detail"].lower()


def test_parse_url_rejects_non_pdf_upstream() -> None:
    """Server returns HTML pretending to be a PDF URL."""
    client_mock = MagicMock()
    client_mock.__enter__ = MagicMock(return_value=client_mock)
    client_mock.__exit__ = MagicMock(return_value=False)
    client_mock.get = MagicMock(
        return_value=_fake_pdf_response(b"<html>nope</html>", content_type="text/html")
    )

    client = TestClient(app)
    with patch(
        "therapist_finder.api.routes.therapists.httpx.Client", return_value=client_mock
    ):
        resp = client.post(
            "/api/therapists/parse-url",
            # Path doesn't end in .pdf so the content-type check is the sole signal.
            json={"url": "https://psych-info.de/some/path"},
        )

    assert resp.status_code == 502
    assert "pdf" in resp.json()["detail"].lower()
