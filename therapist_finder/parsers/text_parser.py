"""Text file parser for therapist data extraction."""

from pathlib import Path

from .base import BaseParser


class TextParser(BaseParser):
    """Parser for extracting therapist information from text files."""
    
    def extract_text(self, file_path: Path) -> str:
        """Extract text content from text file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Text file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
