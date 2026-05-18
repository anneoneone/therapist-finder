"""Tests for /api/contacts/* endpoints and the SQLite contacts store."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from therapist_finder.api import contacts_store
from therapist_finder.api.main import app


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the contacts store at a fresh SQLite file per test."""
    db = tmp_path / "contacts.db"
    monkeypatch.setenv("THERAPIST_FINDER_CONTACTS_DB", str(db))
    contacts_store.init_db()
    yield db


def test_record_contact_is_idempotent(temp_db: Path) -> None:
    client = TestClient(app)
    payload = {"email": "Foo@Example.com", "browser_id": "anon-1"}

    first = client.post("/api/contacts", json=payload)
    assert first.status_code == 200, first.text
    assert first.json() == {"recorded": True}

    second = client.post("/api/contacts", json=payload)
    assert second.status_code == 200
    assert second.json() == {"recorded": False}


def test_counts_aggregates_across_browsers(temp_db: Path) -> None:
    client = TestClient(app)
    client.post("/api/contacts", json={"email": "a@example.com", "browser_id": "b1"})
    client.post("/api/contacts", json={"email": "a@example.com", "browser_id": "b2"})
    client.post("/api/contacts", json={"email": "b@example.com", "browser_id": "b1"})

    resp = client.post(
        "/api/contacts/counts",
        json={"emails": ["a@example.com", "b@example.com", "c@example.com"]},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "counts": {
            "a@example.com": 2,
            "b@example.com": 1,
            "c@example.com": 0,
        }
    }


def test_counts_is_case_insensitive(temp_db: Path) -> None:
    client = TestClient(app)
    client.post(
        "/api/contacts",
        json={"email": "MixedCase@example.com", "browser_id": "b1"},
    )
    resp = client.post(
        "/api/contacts/counts", json={"emails": ["mixedcase@EXAMPLE.com"]}
    )
    assert resp.json()["counts"]["mixedcase@example.com"] == 1


def test_mine_returns_only_this_browser(temp_db: Path) -> None:
    client = TestClient(app)
    client.post("/api/contacts", json={"email": "a@example.com", "browser_id": "alice"})
    client.post("/api/contacts", json={"email": "b@example.com", "browser_id": "alice"})
    client.post("/api/contacts", json={"email": "c@example.com", "browser_id": "bob"})

    alice = client.get("/api/contacts/mine", params={"browser_id": "alice"})
    assert alice.status_code == 200
    assert alice.json() == {"emails": ["a@example.com", "b@example.com"]}

    bob = client.get("/api/contacts/mine", params={"browser_id": "bob"})
    assert bob.json() == {"emails": ["c@example.com"]}


def test_mine_requires_browser_id(temp_db: Path) -> None:
    client = TestClient(app)
    resp = client.get("/api/contacts/mine")
    assert resp.status_code == 422


def test_record_rejects_empty_fields(temp_db: Path) -> None:
    client = TestClient(app)
    resp = client.post("/api/contacts", json={"email": "  ", "browser_id": "anon"})
    # ValueError is mapped to 400 by the global exception handler.
    assert resp.status_code == 400


def test_record_contact_logs_body_when_provided(temp_db: Path) -> None:
    """When body is included, the row also lands in sent_mails."""
    client = TestClient(app)
    resp = client.post(
        "/api/contacts",
        json={
            "email": "doc@example.com",
            "browser_id": "anon-1",
            "body": "Erste Anfrage.",
            "target_lang": "de",
        },
    )
    assert resp.status_code == 200
    prior = contacts_store.get_prior_mails(["doc@example.com"])
    assert prior == {"doc@example.com": ["Erste Anfrage."]}


def test_record_contact_without_body_does_not_log_sent_mail(temp_db: Path) -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/contacts",
        json={"email": "doc@example.com", "browser_id": "anon-1"},
    )
    assert resp.status_code == 200
    assert contacts_store.get_prior_mails(["doc@example.com"]) == {}


def test_get_prior_mails_returns_newest_first_and_limits(temp_db: Path) -> None:
    """Older bodies are dropped beyond limit_per_email."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        contacts_store.record_sent_mail(
            "doc@example.com",
            "anon-1",
            f"Body #{i}",
            target_lang="de",
            now=base + timedelta(minutes=i),
        )

    result = contacts_store.get_prior_mails(["doc@example.com"], limit_per_email=2)
    # Newest first, capped at 2.
    assert result == {"doc@example.com": ["Body #4", "Body #3"]}


def test_get_prior_mails_normalizes_email_case(temp_db: Path) -> None:
    contacts_store.record_sent_mail(
        "Doc@Example.com", "anon-1", "Hi.", target_lang="de"
    )
    result = contacts_store.get_prior_mails(["DOC@example.com"])
    assert result == {"doc@example.com": ["Hi."]}


def test_record_sent_mail_rejects_empty_body(temp_db: Path) -> None:
    with pytest.raises(ValueError):
        contacts_store.record_sent_mail(
            "doc@example.com", "anon-1", "   ", target_lang="de"
        )
