"""Email draft generation functionality."""

from ..config import Settings
from ..models import EmailDraft, TherapistData, UserInfo
from .templates import TemplateManager


class EmailGenerator:
    """Generator for email drafts to therapists."""

    def __init__(self, settings: Settings):
        """Initialize email generator with settings."""
        self.settings = settings
        self.template_manager = TemplateManager(settings)

    def create_drafts(
        self,
        therapists: list[TherapistData],
        user_info: UserInfo,
        template_body: str | None = None,
    ) -> list[EmailDraft]:
        """Create email drafts for therapists with email addresses.

        If ``template_body`` is provided, it is used verbatim instead of
        loading the on-disk default. This is the hook the frontend's
        "Mail template body" step uses to send an edited template.
        """
        template = (
            template_body
            if template_body is not None
            else self.template_manager.load_template()
        )
        drafts = []

        for therapist in therapists:
            if not therapist.email:
                continue

            # Use pre-generated salutation or create one
            salutation = therapist.salutation or self._generate_salutation(
                therapist.name
            )

            # Replace placeholders in template
            email_body = template.replace("<ANREDE>", salutation)
            email_body = self._replace_user_placeholders(email_body, user_info)

            draft = EmailDraft(
                to=therapist.email,
                subject=self.settings.default_subject,
                body=email_body,
                therapist_name=therapist.name,
            )

            drafts.append(draft)

        return drafts

    def _generate_salutation(self, name: str) -> str:
        """Generate appropriate salutation based on therapist name."""
        import re

        title_match = re.search(r"(Dr\.|Dipl\.-Psych\.)", name)
        title = title_match.group(0) if title_match else ""
        last_name = name.split()[-1] if name else ""

        if "Frau" in name:
            return f"Sehr geehrte Frau {title} {last_name}".strip()
        elif "Herr" in name:
            return f"Sehr geehrter Herr {title} {last_name}".strip()
        else:
            return f"Sehr geehrte/r {title} {last_name}".strip()

    def _replace_user_placeholders(self, template: str, user_info: UserInfo) -> str:
        """Replace user information placeholders in template."""
        return template.format(
            name=user_info.name,
            address=user_info.address,
            telefon=user_info.telefon,
            email=user_info.email,
            vermittlungscode=user_info.vermittlungscode,
        )
