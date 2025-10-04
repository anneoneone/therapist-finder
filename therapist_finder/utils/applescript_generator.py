"""AppleScript generation for Mail.app automation."""

import json
from pathlib import Path
from typing import List

from ..models import EmailDraft


def generate_applescript(email_drafts_path: Path, output_path: Path) -> None:
    """Generate AppleScript for creating email drafts in Mail.app."""
    
    # Load email drafts
    with open(email_drafts_path, 'r', encoding='utf-8') as file:
        drafts_data = json.load(file)
    
    # Convert to EmailDraft objects for validation
    drafts = [EmailDraft(**draft) for draft in drafts_data]
    
    # Generate AppleScript
    script = create_applescript_content(drafts)
    
    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as script_file:
        script_file.write(script)


def create_applescript_content(drafts: List[EmailDraft]) -> str:
    """Create AppleScript content for email drafts."""
    script = """
tell application "Mail"
    activate
"""
    
    for draft in drafts:
        # Escape quotes and newlines for AppleScript
        subject = draft.subject.replace('"', '\\"')
        body = draft.body.replace('\n', '\\n').replace('"', '\\"')
        to_address = draft.to
        
        script += f"""
    set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}\\n"}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{to_address}"}}
        save
    end tell
"""
    
    script += "\nend tell\n"
    return script
