"""Tests for email generation."""

from pathlib import Path

import pytest

from therapist_finder.email import EmailGenerator, TemplateManager
from therapist_finder.models import TherapistData


class TestTemplateManager:
    """Tests for template manager."""

    def test_load_template_success(self, test_settings, tmp_path):
        """Test successful template loading."""
        # Create test template
        template_path = tmp_path / "template.txt"
        template_content = "Hello <ANREDE>, this is {name}"
        template_path.write_text(template_content, encoding="utf-8")

        test_settings.email_template_path = template_path
        manager = TemplateManager(test_settings)

        result = manager.load_template()
        assert result == template_content

    def test_load_template_not_found(self, test_settings):
        """Test template file not found."""
        test_settings.email_template_path = Path("nonexistent.txt")
        manager = TemplateManager(test_settings)

        with pytest.raises(FileNotFoundError):
            manager.load_template()


class TestEmailGenerator:
    """Tests for email generator."""

    def test_create_drafts_success(self, test_settings, sample_user_info, tmp_path):
        """Test successful email draft creation."""
        # Create test template
        template_path = tmp_path / "template.txt"
        template_content = "<ANREDE>,\nHello from {name}\nEmail: {email}"
        template_path.write_text(template_content, encoding="utf-8")
        test_settings.email_template_path = template_path

        # Create test therapist
        therapist = TherapistData(
            name="Dr. Frau Test",
            email="therapist@example.com",
            salutation="Sehr geehrte Frau Dr. Test",
        )

        generator = EmailGenerator(test_settings)
        drafts = generator.create_drafts([therapist], sample_user_info)

        assert len(drafts) == 1
        draft = drafts[0]
        assert draft.to == "therapist@example.com"
        assert draft.subject == test_settings.default_subject
        assert "Sehr geehrte Frau Dr. Test" in draft.body
        assert sample_user_info.name in draft.body
        assert sample_user_info.email in draft.body

    def test_create_drafts_no_email(self, test_settings, sample_user_info, tmp_path):
        """Test draft creation with therapist without email."""
        template_path = tmp_path / "template.txt"
        template_path.write_text("<ANREDE>, Hello", encoding="utf-8")
        test_settings.email_template_path = template_path

        # Create therapist without email
        therapist = TherapistData(name="Dr. Test", telefon="123456")

        generator = EmailGenerator(test_settings)
        drafts = generator.create_drafts([therapist], sample_user_info)

        assert len(drafts) == 0
