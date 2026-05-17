"""SQLite-backed log of therapist contact events.

Tracks which therapist emails have been contacted, by which anonymous
browser id, and when. The schema enforces one record per (email, browser_id)
so repeated mailto-opens by the same browser are idempotent.

The store powers two features:
- per-browser dedupe: a user never sees a therapist they personally
  already contacted.
- global balancer: the frontend sorts the send queue ascending by global
  contact count, so therapists nobody has contacted yet appear first.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

_DEFAULT_DB_PATH = Path("contacts.db")


def db_path() -> Path:
    """Resolve the SQLite path from THERAPIST_FINDER_CONTACTS_DB env var."""
    return Path(os.getenv("THERAPIST_FINDER_CONTACTS_DB", str(_DEFAULT_DB_PATH)))


@contextmanager
def _connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    """Create the contacts table and indexes if they do not exist."""
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                browser_id TEXT NOT NULL,
                contacted_at TEXT NOT NULL,
                UNIQUE(email, browser_id)
            );
            CREATE INDEX IF NOT EXISTS idx_contacts_email
                ON contacts(email);
            CREATE INDEX IF NOT EXISTS idx_contacts_browser
                ON contacts(browser_id);
            """
        )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def record_contact(
    email: str,
    browser_id: str,
    *,
    path: Path | None = None,
    now: datetime | None = None,
) -> bool:
    """Record that ``browser_id`` contacted ``email``.

    Returns True if a new row was inserted, False if the pair already existed.
    """
    normalized = _normalize_email(email)
    if not normalized or not browser_id.strip():
        raise ValueError("email and browser_id are required")
    when = (now or datetime.now(timezone.utc)).isoformat()
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO contacts (email, browser_id, contacted_at) "
            "VALUES (?, ?, ?)",
            (normalized, browser_id.strip(), when),
        )
        return bool(cur.rowcount > 0)


def get_counts(
    emails: Iterable[str] | None = None,
    *,
    path: Path | None = None,
) -> dict[str, int]:
    """Return ``{email: contact_count}`` for the given emails (or all)."""
    with _connect(path) as conn:
        if emails is None:
            rows = conn.execute(
                "SELECT email, COUNT(*) AS n FROM contacts GROUP BY email"
            ).fetchall()
            return {row["email"]: row["n"] for row in rows}

        normalized = [_normalize_email(e) for e in emails if e and e.strip()]
        if not normalized:
            return {}
        # `placeholders` is a fixed string of `?,?,?` derived from the count
        # only; all email values are bound via parameters below.
        placeholders = ",".join("?" * len(normalized))
        query = (
            "SELECT email, COUNT(*) AS n FROM contacts "  # nosec B608
            f"WHERE email IN ({placeholders}) GROUP BY email"
        )
        rows = conn.execute(query, normalized).fetchall()
        counts = {row["email"]: row["n"] for row in rows}
        # Fill zeros for asked-about emails that have no contacts yet so the
        # frontend can rely on every requested key being present.
        for email in normalized:
            counts.setdefault(email, 0)
        return counts


def get_user_contacts(browser_id: str, *, path: Path | None = None) -> list[str]:
    """Return emails this browser has already contacted (lowercased)."""
    if not browser_id.strip():
        return []
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT email FROM contacts WHERE browser_id = ? ORDER BY email",
            (browser_id.strip(),),
        ).fetchall()
        return [row["email"] for row in rows]
