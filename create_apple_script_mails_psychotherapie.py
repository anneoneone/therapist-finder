import json
import os
import sys

def create_applescript(email_drafts):
    script = """
    tell application "Mail"
        activate
    """
    for draft in email_drafts:
        to = draft["to"]
        subject = draft["subject"]
        body = draft["body"].replace("\n", "\\n").replace('"', '\\"')
        script += f"""
        set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}\\n"}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{to}"}}
            save
        end tell
        """
    script += "end tell"
    return script

# Get client name from command line argument or prompt for it
if len(sys.argv) > 1:
    client_name = sys.argv[1]
else:
    client_name = input("Enter client name: ")

# Create client directory path
client_dir = os.path.join('clients', client_name.replace(' ', '_').lower())
email_drafts_path = os.path.join(client_dir, 'email_drafts.json')
applescript_path = os.path.join(client_dir, 'create_email_drafts.scpt')

# Check if email drafts file exists
if not os.path.exists(email_drafts_path):
    print(f"Error: {email_drafts_path} not found. Please run parse_psychotherapie.py first.")
    sys.exit(1)

# Load email drafts from JSON
with open(email_drafts_path, 'r', encoding='utf-8') as email_file:
    email_drafts = json.load(email_file)

# Create AppleScript
applescript = create_applescript(email_drafts)

# Save AppleScript to file in client directory
with open(applescript_path, 'w', encoding='utf-8') as script_file:
    script_file.write(applescript)

print(f"AppleScript file '{applescript_path}' created.")
