import json
import os
import re
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
CLIENT_FILE = ROOT / "gmail-oauth-client.json"
ENV_FILE = ROOT / ".env"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

if not CLIENT_FILE.is_file():
    raise SystemExit("OAuth client file is missing.")

client_data = json.loads(CLIENT_FILE.read_text())
client = client_data.get("installed")

if not client:
    raise SystemExit("The OAuth file is not a Desktop client.")

sender_email = input("Enter the Gmail address Nestify will send from: ").strip()
if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", sender_email):
    raise SystemExit("Please enter a valid email address.")

flow = InstalledAppFlow.from_client_secrets_file(
    str(CLIENT_FILE),
    scopes=SCOPES,
)

print("\nOpening Google's authorization flow...")
credentials = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent",
)

if not credentials.refresh_token:
    raise SystemExit(
        "Google did not return a refresh token. No credentials were saved."
    )

updates = {
    "GMAIL_CLIENT_ID": client["client_id"],
    "GMAIL_CLIENT_SECRET": client["client_secret"],
    "GMAIL_REFRESH_TOKEN": credentials.refresh_token,
    "GMAIL_SENDER_EMAIL": sender_email,
}

lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
for key, value in updates.items():
    encoded = f"{key}={json.dumps(value)}"
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index, line in enumerate(lines):
        if pattern.match(line):
            lines[index] = encoded
            break
    else:
        lines.append(encoded)

ENV_FILE.write_text("\n".join(lines) + "\n")
os.chmod(ENV_FILE, 0o600)

print("\nOAuth authorization successful.")
print("Gmail settings saved to .env.")
print("Credentials were not displayed.")
