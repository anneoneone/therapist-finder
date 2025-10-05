"""PDF parser for therapist data extraction."""

from pathlib import Path

from .base import BaseParser


class PDFParser(BaseParser):
    """Parser for extracting therapist information from PDF files."""

    def extract_text(self, file_path: Path) -> str:
        """Extract text content from PDF file."""
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        try:
            # Try pdfplumber first (better text extraction)
            import pdfplumber

            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text

        except ImportError:
            try:
                # Fallback to PyPDF2
                import PyPDF2

                text = ""
                with open(file_path, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                return text

            except ImportError as err:
                raise ImportError(
                    "PDF parsing requires either 'pdfplumber' or 'PyPDF2'. "
                    "Install with: poetry add pdfplumber"
                ) from err
