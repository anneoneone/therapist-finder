# Therapist Finder

A modern Python tool for parsing therapist data from PDF/text files and generating personalized email drafts.

## Features

- 📄 Parse therapist data from PDF and text files
- ✉️ Generate personalized email drafts
- 📊 Export data to JSON and Markdown formats
- 🍎 Generate AppleScript for Mail.app automation
- 🔧 Modern Python project structure with Poetry
- 🎨 Rich CLI interface with progress bars
- 🧪 Comprehensive testing with pytest

## Installation

### Prerequisites

- Python 3.9 or higher
- Poetry (recommended) or pip

### Using Poetry (Recommended)

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry env activate
```

### Using pip

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

```bash
# Parse a PDF file
therapist-finder process --pdf path/to/therapists.pdf

# Parse a text file
therapist-finder process --text path/to/therapists.txt

# Generate AppleScript for existing client
therapist-finder applescript --client "John Doe"

# Show help
therapist-finder --help
```

### Python API

```python
from therapist_finder import TherapistParser, EmailGenerator
from therapist_finder.config import Settings

# Initialize components
parser = TherapistParser()
email_gen = EmailGenerator()
settings = Settings()

# Parse PDF
therapists = parser.parse_pdf("therapists.pdf")

# Generate emails
emails = email_gen.create_drafts(therapists, user_info)
```

## Configuration

Configuration can be managed through:

1. Environment variables
2. `config.yaml` file
3. Command line arguments

Example `config.yaml`:

```yaml
email_template_path: "templates/email_template.txt"
output_directory: "clients"
default_subject: "Terminanfrage"
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd therapist-finder

# Install development dependencies
poetry install --with dev

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=therapist_finder

# Run specific test file
poetry run pytest tests/test_parser.py
```

### Code Quality

```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check .

# Type checking
poetry run mypy therapist_finder
```

## Project Structure

```
therapist-finder/
├── therapist_finder/           # Main package
│   ├── __init__.py
│   ├── cli.py                  # CLI interface
│   ├── config.py               # Configuration management
│   ├── models.py               # Data models
│   ├── parsers/                # Parser modules
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── pdf_parser.py
│   │   └── text_parser.py
│   ├── email/                  # Email generation
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── templates.py
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       ├── file_utils.py
│       └── text_utils.py
├── templates/                  # Email templates
│   └── email_template.txt
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_parsers.py
│   └── test_email.py
├── clients/                    # Client data (gitignored)
├── pyproject.toml              # Poetry configuration
├── README.md                   # This file
└── .gitignore                  # Git ignore rules
```

## License

MIT License - see LICENSE file for details.
