"""Therapist Finder - Modern tool for parsing therapist data."""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .config import Settings
from .email import EmailGenerator
from .models import EmailDraft, TherapistData, UserInfo
from .parsers import PDFParser, TextParser

__all__ = [
    "TherapistData",
    "UserInfo",
    "EmailDraft",
    "PDFParser",
    "TextParser",
    "EmailGenerator",
    "Settings",
]
