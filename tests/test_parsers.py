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
