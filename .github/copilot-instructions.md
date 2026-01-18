# Therapist-Finder Project Instructions

## Project Overview

A Python CLI tool for parsing therapist data from PDF/text files and generating personalized email drafts with AppleScript automation for macOS Mail.app.

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.10+ |
| Package Manager | Poetry |
| CLI Framework | Typer with Rich |
| Data Validation | Pydantic 2.x, pydantic-settings |
| PDF Parsing | pdfplumber |
| Testing | pytest, pytest-cov |
| Linting | Black, Ruff, mypy |
| Docstrings | Google style (pydocstyle) |

## Commands

```bash
# Install dependencies
poetry install

# Run CLI
poetry run therapist-finder process --pdf <file>
poetry run therapist-finder process --text <file>
poetry run therapist-finder applescript --client "Name"

# Testing
poetry run pytest -ra -q --strict-markers

# Linting & Formatting
poetry run black .
poetry run ruff check .
poetry run ruff check . --fix
poetry run mypy .

# Pre-commit hooks
poetry run pre-commit run --all-files
```

## Project Structure

```
therapist_finder/
├── cli.py              # Typer CLI entry point
├── config.py           # pydantic-settings configuration
├── models.py           # Pydantic data models (Therapist, UserInfo, EmailDraft)
├── email/
│   ├── generator.py    # Email draft generation
│   └── templates.py    # Template loading/saving
├── parsers/
│   ├── base.py         # Abstract base parser with state machine
│   ├── pdf_parser.py   # PDF text extraction (pdfplumber)
│   └── text_parser.py  # Plain text file parsing
└── utils/
    ├── applescript_generator.py  # macOS Mail.app automation
    ├── file_utils.py             # JSON/Markdown export
    └── text_utils.py             # Filename sanitization, title extraction

tests/
├── conftest.py         # pytest fixtures
├── test_email.py       # Email generation tests
└── test_parsers.py     # Parser tests

templates/
└── email_template.txt  # Email template with placeholders
```

## Code Standards

### Type Hints
All functions must have type hints:
```python
def parse_therapist(text: str) -> Therapist:
    """Parse therapist data from text."""
    ...
```

### Docstrings (Google Style)
```python
def generate_email(therapist: Therapist, user_info: UserInfo) -> EmailDraft:
    """Generate a personalized email draft.

    Args:
        therapist: The therapist to contact.
        user_info: User's personal information.

    Returns:
        A complete email draft ready to send.

    Raises:
        ValueError: If therapist has no email address.
    """
```

### Pydantic Models
```python
from pydantic import BaseModel, Field

class Therapist(BaseModel):
    """Therapist contact information."""

    name: str = Field(..., description="Full name")
    email: str | None = Field(None, description="Email address")
```

### Error Handling
```python
from rich.console import Console

console = Console(stderr=True)

try:
    result = parse_file(path)
except FileNotFoundError:
    console.print(f"[red]Error:[/red] File not found: {path}")
    raise typer.Exit(1)
```

## Boundaries

### ✅ Always
- Run `pytest -ra -q` before committing
- Use type hints on all functions
- Follow Google docstring style
- Use `pathlib.Path` for file operations
- Use Rich for CLI output formatting

### ⚠️ Ask First
- Modifying Pydantic models in `models.py`
- Changing CLI command signatures in `cli.py`
- Altering email template placeholders
- Adding new dependencies to `pyproject.toml`

### 🚫 Never
- Commit secrets, API keys, or credentials
- Modify `.env` files or environment variable names in `config.py` without approval
- Remove existing tests without replacement
- Use `print()` instead of Rich console output
