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
