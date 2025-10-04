"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from therapist_finder.config import Settings
from therapist_finder.models import UserInfo, TherapistData


@pytest.fixture
def test_settings():
    """Test settings with temporary paths."""
    return Settings(
        email_template_path=Path("templates/email_template.txt"),
        output_directory=Path("test_clients"),
        default_subject="Test Subject",
        max_address_parts=2,
        json_indent=2
    )


@pytest.fixture
def sample_user_info():
    """Sample user information for testing."""
    return UserInfo(
        name="Max Mustermann",
        email="max@example.com",
        telefon="0123456789",
        address="Musterstraße 1, 12345 Berlin",
        vermittlungscode="TEST-123"
    )


@pytest.fixture
def sample_therapist():
    """Sample therapist data for testing."""
    return TherapistData(
        name="Dr. Frau Beispiel",
        address="Beispielstraße 1, 12345 Berlin",
        telefon="0987654321",
        email="dr.beispiel@example.com",
        therapieform=["Verhaltenstherapie"],
        sprechzeiten=["Mo-Fr 9-17 Uhr"],
        salutation="Sehr geehrte Frau Dr. Beispiel"
    )
