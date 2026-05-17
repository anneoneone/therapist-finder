"""Base parser class for therapist data extraction."""

from abc import ABC, abstractmethod
from pathlib import Path
import re
from typing import Any

from ..config import Settings
from ..models import TherapistData


class BaseParser(ABC):
    """Abstract base class for therapist data parsers."""

    def __init__(self, settings: Settings):
        """Initialize parser with settings."""
        self.settings = settings
        self.seen_emails: set[str] = set()
        self.current_entry: dict[str, Any] = {}
        self.current_section: str = ""

    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """Extract text content from file."""
        pass

    def parse_file(self, file_path: Path) -> list[TherapistData]:
        """Parse file and return list of therapist data."""
        self._reset_state()
        text = self.extract_text(file_path)
        return self.parse_text_content(text)

    def _reset_state(self) -> None:
        """Reset parser state for new parsing session."""
        self.seen_emails.clear()
        self.current_entry.clear()
        self.current_section = ""

    def _is_therapist_header(self, line: str) -> bool:
        """Check if line contains therapist profession header."""
        return line.startswith("Psychologische Psychotherapeutin") or line.startswith(
            "Psychologischer Psychotherapeut"
        )

    def _extract_phone(self, line: str) -> str:
        """Extract phone number from line."""
        if line.startswith("Tel.:"):
            return line.split("Tel.:")[1].strip()
        return ""

    def _extract_email(self, line: str) -> str:
        """Extract email address from line."""
        if line.startswith("E-Mail:"):
            email = line.split("E-Mail:")[1].strip()
            return email
        return ""

    def _generate_salutation(self, name: str) -> str:
        """Generate appropriate salutation based on name."""
        title_match = re.search(r"(Dr\.|Dipl\.-Psych\.)", name)
        title = title_match.group(0) if title_match else ""
        last_name = name.split()[-1] if name else ""

        if "Frau" in name:
            return f"Sehr geehrte Frau {title} {last_name}".strip()
        elif "Herr" in name:
            return f"Sehr geehrter Herr {title} {last_name}".strip()
        else:
            return f"Sehr geehrte/r {title} {last_name}".strip()

    def _should_add_entry(self, entry: dict[str, Any]) -> bool:
        """Check if entry should be added (no duplicate emails)."""
        email = entry.get("email", "")
        if not email:
            return True

        if email in self.seen_emails or entry.get("duplicate_email", False):
            return False

        self.seen_emails.add(email)
        return True

    def _finalize_entry(self, data: list[TherapistData]) -> None:
        """Finalize current entry and add to data if valid."""
        if self.current_entry and self._should_add_entry(self.current_entry):
            # Generate salutation
            if "name" in self.current_entry:
                self.current_entry["salutation"] = self._generate_salutation(
                    self.current_entry["name"]
                )

            # Create TherapistData object
            try:
                therapist = TherapistData(**self.current_entry)
                data.append(therapist)
            except Exception as e:
                # Log validation error but continue
                print(f"Warning: Failed to create therapist entry: {e}")

        # Reset for next entry
        self.current_entry.clear()
        self.current_section = ""

    def parse_text_content(self, text: str) -> list[TherapistData]:
        """Parse extracted text content into structured data.

        Dispatches to the right strategy based on a content marker. The
        Psych-Info Resultate format has no profession header or field labels
        so the KV Berlin state machine produces zero entries for it.
        """
        if "Psych-Info Resultate" in text:
            return self._parse_psych_info(text)
        return self._parse_kv_berlin(text)

    def _parse_kv_berlin(self, text: str) -> list[TherapistData]:
        """Parse KV-Berlin-style PDFs (profession headers + `Tel.:` / `E-Mail:`)."""
        lines = text.split("\n")
        data: list[TherapistData] = []

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Check for new therapist entry
            if self._is_therapist_header(line):
                self._finalize_entry(data)
                self.current_section = "name"
                continue

            # Parse name section
            if self.current_section == "name":
                self.current_entry["name"] = line
                self.current_section = "address"
                continue

            # Parse address section
            if self.current_section == "address":
                if "address" not in self.current_entry:
                    self.current_entry["address"] = line
                else:
                    self.current_entry["address"] += ", " + line

                # Check if address is complete
                address_parts = self.current_entry["address"].split(", ")
                if len(address_parts) >= self.settings.max_address_parts:
                    self.current_section = ""
                continue

            # Parse phone number
            phone = self._extract_phone(line)
            if phone:
                self.current_entry["telefon"] = phone
                continue

            # Parse email
            email = self._extract_email(line)
            if email:
                if email not in self.seen_emails:
                    self.current_entry["email"] = email
                else:
                    self.current_entry["duplicate_email"] = True
                continue

            # Parse therapy forms
            if line == "Psychotherapie":
                self.current_section = "therapieform"
                self.current_entry["therapieform"] = []
                continue

            if self.current_section == "therapieform":
                if line.startswith("Sprechzeiten"):
                    self.current_section = "sprechzeiten"
                    self.current_entry["sprechzeiten"] = []
                    continue
                self.current_entry["therapieform"].append(line)
                continue

            # Parse office hours
            if self.current_section == "sprechzeiten":
                if self._is_therapist_header(line):
                    self._finalize_entry(data)
                    self.current_section = "name"
                    continue
                self.current_entry["sprechzeiten"].append(line)
                continue

        # Don't forget the last entry
        self._finalize_entry(data)

        return data

    _PSYCH_INFO_ENTRY_MARKER = re.compile(r"^\s*\d+\s*\.\s*$")
    _PSYCH_INFO_DISTANCE_LINE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*km\s*$")
    _PSYCH_INFO_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
    _PSYCH_INFO_PHONE_SHAPE = re.compile(r"^[\d\s\-/()\.+]+$")

    def _parse_psych_info(self, text: str) -> list[TherapistData]:
        """Parse Psych-Info Resultate PDFs.

        Entries are introduced by a numbered marker line (``1 .``, ``2 .`` …),
        optionally preceded by a distance line (``0.05 km``). Each block has
        name, address, and a free mix of phone / email / Sprechzeiten lines
        which are classified by content.
        """
        lines = [line.strip() for line in text.split("\n")]
        data: list[TherapistData] = []

        # Locate every entry-marker index along with its captured distance.
        markers: list[tuple[int, float | None]] = []
        for idx, line in enumerate(lines):
            if not self._PSYCH_INFO_ENTRY_MARKER.match(line):
                continue
            distance: float | None = None
            for back in range(idx - 1, -1, -1):
                if not lines[back]:
                    continue
                m = self._PSYCH_INFO_DISTANCE_LINE.match(lines[back])
                if m:
                    distance = float(m.group(1))
                break
            markers.append((idx, distance))

        for i, (start, distance) in enumerate(markers):
            end = markers[i + 1][0] if i + 1 < len(markers) else len(lines)
            # Skip the preceding distance line (if any) so it doesn't land in
            # the next block when we slice.
            block_end = end
            if i + 1 < len(markers):
                prev = end - 1
                while prev > start and not lines[prev]:
                    prev -= 1
                if self._PSYCH_INFO_DISTANCE_LINE.match(lines[prev]):
                    block_end = prev

            block = [ln for ln in lines[start + 1 : block_end] if ln]
            if len(block) < 2:
                continue

            self.current_entry = {
                "name": block[0],
                "address": block[1],
                "sources": ["psych_info"],
            }
            if distance is not None:
                self.current_entry["distance_km"] = distance

            sprechzeiten: list[str] = []
            for line in block[2:]:
                email_match = self._PSYCH_INFO_EMAIL.search(line)
                if email_match:
                    email = email_match.group(0)
                    if email in self.seen_emails:
                        self.current_entry["duplicate_email"] = True
                    else:
                        self.current_entry["email"] = email
                    continue
                if (
                    self._PSYCH_INFO_PHONE_SHAPE.match(line)
                    and sum(c.isdigit() for c in line) >= 6
                ):
                    self.current_entry["telefon"] = line
                    continue
                sprechzeiten.append(line)

            if sprechzeiten:
                self.current_entry["sprechzeiten"] = sprechzeiten

            self._finalize_entry(data)

        return data
