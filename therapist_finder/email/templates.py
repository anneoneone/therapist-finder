"""Email template management."""

from pathlib import Path

from ..config import Settings


class TemplateManager:
    """Manager for email templates."""

    def __init__(self, settings: Settings):
        """Initialize template manager with settings."""
        self.settings = settings

    def load_template(self, path: Path | None = None) -> str:
        """Load email template from file."""
        template_path = self.settings.email_template_path

        if not template_path.exists():
            raise FileNotFoundError(
                f"Email template file not found: {template_path}\n"
                f"Please create the template file or update the configuration."
            )

        with open(template_path, encoding="utf-8") as file:
            return file.read()

    def save_template(self, content: str, path: Path | None = None) -> None:
        """Save email template to file."""
        template_path = path or self.settings.email_template_path
        template_path.parent.mkdir(parents=True, exist_ok=True)

        with open(template_path, "w", encoding="utf-8") as file:
            file.write(content)
