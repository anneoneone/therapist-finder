"""File handling utilities."""

import json
from pathlib import Path
from typing import List, Any

from ..models import TherapistData


def save_json(data: Any, file_path: Path, indent: int = 4) -> None:
    """Save data to JSON file with proper encoding."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=indent)


def save_markdown(therapists: List[TherapistData], file_path: Path) -> None:
    """Save therapist data as markdown table."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as md_file:
        # Write headers
        headers = [
            "Name", "Adresse", "Telefon", "E-Mail", "Therapieform", 
            "Sprechzeiten", "Kontaktiert", "Datum", "Status"
        ]
        md_file.write("| " + " | ".join(headers) + " |\n")
        md_file.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        
        # Write data rows
        for therapist in therapists:
            name = therapist.name
            address = therapist.address or ""
            telefon = therapist.telefon or ""
            email = str(therapist.email) if therapist.email else ""
            therapieform = "<br>".join(therapist.therapieform)
            sprechzeiten = "<br>".join(therapist.sprechzeiten)
            kontaktiert = ""  # Placeholder
            datum = ""  # Placeholder
            status = ""  # Placeholder
            
            row = [
                name, address, telefon, email, therapieform, 
                sprechzeiten, kontaktiert, datum, status
            ]
            md_file.write("| " + " | ".join(row) + " |\n")
