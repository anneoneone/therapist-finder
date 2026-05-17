"""Tests for parser modules."""

from pathlib import Path

import pytest

from therapist_finder.parsers import PDFParser, TextParser


class TestTextParser:
    """Tests for text parser."""

    def test_extract_text_success(self, test_settings, tmp_path):
        """Test successful text extraction."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "Test content\nLine 2"
        test_file.write_text(test_content, encoding="utf-8")

        parser = TextParser(test_settings)
        result = parser.extract_text(test_file)

        assert result == test_content

    def test_extract_text_file_not_found(self, test_settings):
        """Test file not found error."""
        parser = TextParser(test_settings)

        with pytest.raises(FileNotFoundError):
            parser.extract_text(Path("nonexistent.txt"))

    def test_parse_simple_therapist(self, test_settings, tmp_path):
        """Test parsing simple therapist entry."""
        test_content = """Psychologische Psychotherapeutin
Dr. Frau Mustermann
Musterstraße 1
12345 Berlin
Tel.: 0123456789
E-Mail: test@example.com
Psychotherapie
Verhaltenstherapie
Sprechzeiten
Mo-Fr 9-17 Uhr"""

        test_file = tmp_path / "test.txt"
        test_file.write_text(test_content, encoding="utf-8")

        parser = TextParser(test_settings)
        therapists = parser.parse_file(test_file)

        assert len(therapists) == 1
        therapist = therapists[0]
        assert therapist.name == "Dr. Frau Mustermann"
        assert therapist.address == "Musterstraße 1, 12345 Berlin"
        assert therapist.telefon == "0123456789"
        assert therapist.email == "test@example.com"
        assert "Verhaltenstherapie" in therapist.therapieform
        assert "Mo-Fr 9-17 Uhr" in therapist.sprechzeiten


class TestPDFParser:
    """Tests for PDF parser."""

    def test_extract_text_file_not_found(self, test_settings):
        """Test file not found error."""
        parser = PDFParser(test_settings)

        with pytest.raises(FileNotFoundError):
            parser.extract_text(Path("nonexistent.pdf"))


PSYCH_INFO_SAMPLE = """Psych-Info Resultate
Standort: 12047, Neukölln, Berlin, Deutschland
0.05 km
1 .
Katrin Nicolaus
Reuterstraße 37, Berlin Neukölln, 12047
030-20988094
therapie_nicolaus@yahoo.com
0.16 km
2 .
Heike Paschotta
Pflügerstr. 18/Gewerbehof, Berlin Reuterkiez, 12047
01575-3127606
Frau H. Paschotta Do 8:30-09:30 Fr 15:00-16:00
nachmittags nach Vereinbarung
praxis@paschotta.de
0.17 km
3 .
Lena Amende
Hobrechtstraße 21, Berlin Neukölln, 12047
01774135249
"""


class TestPsychInfoFormat:
    """Tests for the Psych-Info Resultate PDF format."""

    def test_full_entry(self, test_settings):
        """Entry with all fields parses cleanly."""
        parser = TextParser(test_settings)
        therapists = parser.parse_text_content(PSYCH_INFO_SAMPLE)

        first = therapists[0]
        assert first.name == "Katrin Nicolaus"
        assert first.address == "Reuterstraße 37, Berlin Neukölln, 12047"
        assert first.telefon == "030-20988094"
        assert first.email == "therapie_nicolaus@yahoo.com"
        assert first.distance_km == 0.05
        assert first.sources == ["psych_info"]

    def test_multiline_sprechzeiten(self, test_settings):
        """Office hours spanning multiple lines accumulate."""
        parser = TextParser(test_settings)
        therapists = parser.parse_text_content(PSYCH_INFO_SAMPLE)

        paschotta = therapists[1]
        assert paschotta.name == "Heike Paschotta"
        assert paschotta.telefon == "01575-3127606"
        assert paschotta.email == "praxis@paschotta.de"
        assert paschotta.sprechzeiten == [
            "Frau H. Paschotta Do 8:30-09:30 Fr 15:00-16:00",
            "nachmittags nach Vereinbarung",
        ]

    def test_entry_without_email(self, test_settings):
        """Entries with no email still emit (email stays None)."""
        parser = TextParser(test_settings)
        therapists = parser.parse_text_content(PSYCH_INFO_SAMPLE)

        amende = therapists[2]
        assert amende.name == "Lena Amende"
        assert amende.telefon == "01774135249"
        assert amende.email is None
        assert amende.sprechzeiten == []
        assert amende.distance_km == 0.17
