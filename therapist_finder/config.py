"""Configuration management for therapist finder."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="THERAPIST_FINDER_"
    )
    
    # File paths
    email_template_path: Path = Field(
        default=Path("templates/email_template.txt"),
        description="Path to email template file"
    )
    output_directory: Path = Field(
        default=Path("clients"),
        description="Directory for client output files"
    )
    
    # Email settings
    default_subject: str = Field(
        default="Terminanfrage",
        description="Default email subject"
    )
    
    # Parser settings
    max_address_parts: int = Field(
        default=2,
        description="Maximum number of address parts to combine"
    )
    
    # Output settings
    json_indent: int = Field(
        default=4,
        description="JSON indentation for output files"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    def get_client_directory(self, client_name: str) -> Path:
        """Get client-specific output directory."""
        safe_name = client_name.replace(" ", "_").replace("/", "_").lower()
        return self.output_directory / safe_name
    
    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.email_template_path.parent.mkdir(parents=True, exist_ok=True)
