"""Text processing utilities."""

import re


def sanitize_filename(filename: str) -> str:
    """Sanitize string for use as filename."""
    # Replace spaces and special characters
    sanitized = re.sub(r'[^\w\s-]', '', filename)
    sanitized = re.sub(r'[-\s]+', '_', sanitized)
    return sanitized.lower().strip('_')


def extract_title_from_name(name: str) -> tuple[str, str]:
    """Extract title and last name from full name."""
    title_match = re.search(r'(Dr\.|Dipl\.-Psych\.)', name)
    title = title_match.group(0) if title_match else ""
    last_name = name.split()[-1] if name else ""
    return title, last_name
