"""Command-line interface for therapist finder."""

from pathlib import Path

from rich import print as rprint
from rich.console import Console
from rich.table import Table
import typer

from .config import Settings
from .email import EmailGenerator
from .models import EmailDraft, TherapistData, UserInfo
from .parsers import PDFParser, TextParser
from .utils.file_utils import save_json, save_markdown

app = typer.Typer(help="Parse therapist data and generate email drafts")
console = Console()


def get_user_info() -> UserInfo:
    """Interactive user information collection."""
    console.print("\n[bold blue]Please enter your personal information:[/bold blue]")

    name = typer.prompt("Name")
    email = typer.prompt("Email")
    telefon = typer.prompt("Phone number")
    address = typer.prompt("Address")
    vermittlungscode = typer.prompt("Vermittlungscode")

    return UserInfo(
        name=name,
        email=email,
        telefon=telefon,
        address=address,
        vermittlungscode=vermittlungscode,
    )


@app.command()
def process(
    pdf_path: Path | None = typer.Option(None, "--pdf", help="PDF file to process"),
    text_path: Path | None = typer.Option(None, "--text", help="Text file to process"),
    config_path: Path | None = typer.Option(None, "--config", help="Config file path"),
    output_dir: Path | None = typer.Option(None, "--output", help="Output directory"),
) -> None:
    """Process therapist data from PDF or text file."""
    # Validate input
    if not pdf_path and not text_path:
        rprint("[red]Error: Please specify either --pdf or --text file[/red]")
        raise typer.Exit(1)

    if pdf_path and text_path:
        rprint("[red]Error: Please specify only one input file[/red]")
        raise typer.Exit(1)

    input_file = pdf_path or text_path
    if input_file is not None and not input_file.exists():
        rprint(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)

    # Load settings
    settings = Settings()
    if output_dir:
        settings.output_directory = output_dir

    # Get user information
    user_info = get_user_info()

    # Create client directory
    client_dir = settings.get_client_directory(user_info.name)
    client_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[green]Created client directory: {client_dir}[/green]")

    # Parse file
    with console.status("[bold green]Parsing file..."):
        if pdf_path:
            therapists = PDFParser(settings).parse_file(pdf_path)
        elif text_path:
            therapists = TextParser(settings).parse_file(text_path)
        else:
            console.print("[red]Error: Either PDF or text file must be provided[/red]")
            raise typer.Exit(1)

    console.print(f"[green]Parsed {len(therapists)} therapist entries[/green]")

    # Save parsed data
    parsed_data_path = client_dir / "parsed_data.json"
    save_json([t.dict() for t in therapists], parsed_data_path, settings.json_indent)

    # Create markdown table
    markdown_path = client_dir / "parsed_data.md"
    save_markdown(therapists, markdown_path)

    # Generate emails
    email_gen = EmailGenerator(settings)
    email_drafts = email_gen.create_drafts(therapists, user_info)

    console.print(f"[green]Generated {len(email_drafts)} email drafts[/green]")

    # Save email drafts
    email_drafts_path = client_dir / "email_drafts.json"
    save_json([e.dict() for e in email_drafts], email_drafts_path, settings.json_indent)

    # Show statistics
    show_statistics(therapists, email_drafts)

    console.print("\n[bold green]Processing completed![/bold green]")
    console.print(f"[blue]All files saved to: {client_dir}[/blue]")


@app.command()
def applescript(
    client: str = typer.Argument(help="Client name"),
    config_file: Path | None = typer.Option(None, "--config", help="Config file path"),
) -> None:
    """Generate AppleScript for existing client email drafts."""
    settings = Settings()
    client_dir = settings.get_client_directory(client)

    email_drafts_path = client_dir / "email_drafts.json"
    if not email_drafts_path.exists():
        rprint(f"[red]Error: Email drafts not found for client '{client}'[/red]")
        rprint(f"[yellow]Expected file: {email_drafts_path}[/yellow]")
        raise typer.Exit(1)

    # Import here to avoid circular imports
    from .utils.applescript_generator import generate_applescript

    script_path = client_dir / "create_email_drafts.scpt"
    generate_applescript(email_drafts_path, script_path)

    console.print(f"[green]AppleScript generated: {script_path}[/green]")


def show_statistics(
    therapists: list[TherapistData], email_drafts: list[EmailDraft]
) -> None:
    """Display parsing and generation statistics."""
    table = Table(title="Processing Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")

    total = len(therapists)
    with_email = sum(1 for t in therapists if t.email)
    with_phone = sum(1 for t in therapists if t.telefon)

    table.add_row("Total entries", str(total))
    table.add_row("With email", str(with_email))
    table.add_row("With phone", str(with_phone))
    table.add_row("Email drafts generated", str(len(email_drafts)))

    console.print("\n")
    console.print(table)


@app.command()
def search_116117(
    specialty: str = typer.Option(
        "Psychotherapeut", "--specialty", "-s", help="Therapist specialty"
    ),
    location: str = typer.Option(..., "--location", "-l", help="City or postal code"),
    radius: int = typer.Option(25, "--radius", "-r", help="Search radius in km"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
    output_dir: Path | None = typer.Option(None, "--output", help="Output directory"),
) -> None:
    """Search for therapists using arztsuche.116117.de API."""
    try:
        from .parsers.arztsuche_api import Arztsuche116117Client, SearchParams
    except ImportError as err:
        rprint(
            "[red]Error: httpx is required for API access. Install with: poetry add httpx[/red]"
        )
        raise typer.Exit(1) from err

    console.print(
        f"\n[bold blue]Searching for {specialty} in {location}...[/bold blue]"
    )

    # Create search parameters
    params = SearchParams(
        specialty=specialty,
        location=location,
        radius=radius,
        max_results=max_results,
    )

    # Search using API
    try:
        with Arztsuche116117Client() as client:
            therapists = client.search_therapists(params)
    except Exception as e:
        rprint(f"[red]Error: API request failed: {e}[/red]")
        raise typer.Exit(1) from e

    if not therapists:
        rprint("[yellow]No therapists found[/yellow]")
        raise typer.Exit(0)

    # Display results
    table = Table(title=f"Found {len(therapists)} therapists")
    table.add_column("Name", style="cyan")
    table.add_column("Address", style="green")
    table.add_column("Phone", style="yellow")
    table.add_column("Distance", style="magenta")

    for t in therapists:
        address = f"{t.street or ''}, {t.postal_code or ''} {t.city or ''}".strip(", ")
        distance = f"{t.distance:.1f} km" if t.distance else "-"
        table.add_row(t.name, address, t.phone or "-", distance)

    console.print("\n")
    console.print(table)

    # Save results if output directory specified
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        therapist_list = [
            TherapistData(
                name=t.name,
                address=f"{t.street or ''}, {t.postal_code or ''} {t.city or ''}".strip(
                    ", "
                ),
                telefon=t.phone or None,
                email=t.email or None,
            )
            for t in therapists
        ]

        json_path = output_dir / "therapists_116117.json"
        md_path = output_dir / "therapists_116117.md"

        save_json([td.model_dump() for td in therapist_list], json_path)
        save_markdown(therapist_list, md_path)

        console.print("\n[green]✓ Results saved to:[/green]")
        console.print(f"  JSON: {json_path}")
        console.print(f"  Markdown: {md_path}")


if __name__ == "__main__":
    app()
