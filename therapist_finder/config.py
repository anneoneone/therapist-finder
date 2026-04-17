"""Configuration management for therapist finder."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="THERAPIST_FINDER_",
    )

    # File paths
    email_template_path: Path = Field(
        default=Path("templates/email_template.txt"),
        description="Path to email template file",
    )
    output_directory: Path = Field(
        default=Path("clients"), description="Directory for client output files"
    )

    # Email settings
    default_subject: str = Field(
        default="Terminanfrage", description="Default email subject"
    )

    # Parser settings
    max_address_parts: int = Field(
        default=2, description="Maximum number of address parts to combine"
    )

    # Output settings
    json_indent: int = Field(default=4, description="JSON indentation for output files")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Source / scraper settings
    enabled_sources: list[str] = Field(
        default_factory=lambda: ["116117", "osm"],
        description=(
            "Default data sources for crawl-berlin. "
            "CI-safe; residential-only sources (psych_info, therapie_de) "
            "must be opted into explicitly."
        ),
    )
    residential_only_sources: list[str] = Field(
        default_factory=lambda: ["psych_info", "therapie_de"],
        description=(
            "Sources that only work from residential IPs. Enabling them "
            "from cloud / CI runners will return empty results."
        ),
    )
    default_max_results: int = Field(
        default=20, description="Default N closest providers to return"
    )
    scraper_user_agent: str = Field(
        default=(
            "therapist-finder/0.1 "
            "(+https://github.com/anneoneone/therapist-finder)"
        ),
        description="User-Agent sent by scrapers and geocoder",
    )
    scraper_min_delay_seconds: float = Field(
        default=2.0, description="Minimum delay between requests to a given host"
    )
    overpass_endpoint: str = Field(
        default="https://overpass-api.de/api/interpreter",
        description="Overpass API endpoint",
    )
    nominatim_endpoint: str = Field(
        default="https://nominatim.openstreetmap.org/search",
        description="Nominatim geocoding endpoint",
    )
    http_cache_dir: Path | None = Field(
        default=Path(".cache/therapist-finder"),
        description="Directory for caching HTTP responses",
    )

    def get_client_directory(self, client_name: str) -> Path:
        """Get client-specific output directory."""
        safe_name = client_name.replace(" ", "_").replace("/", "_").lower()
        return self.output_directory / safe_name

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.email_template_path.parent.mkdir(parents=True, exist_ok=True)
