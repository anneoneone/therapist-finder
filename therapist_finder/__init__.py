"""Therapist Finder - Modern tool for parsing therapist data."""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .models import TherapistData, UserInfo, EmailDraft
from .parsers import PDFParser, TextParser
from .email import EmailGenerator
from .config import Settings

__all__ = [
    "TherapistData",
    "UserInfo", 
    "EmailDraft",
    "PDFParser",
    "TextParser",
    "EmailGenerator",
    "Settings",
]
