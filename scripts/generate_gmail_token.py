
import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


GMAIL_SEND_SCOPE = (
    "https://www.googleapis.com/auth/gmail.send"
)


def validate_credentials_file(credentials_path):
    """Ensure the downloaded OAuth client is a Desktop client."""

    path = Path(credentials_path)

    if not path.exists():
        raise FileNotFoundError(
            f"OAuth credentials file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if "installed" not in data:
        raise ValueError(
            "The OAuth credentials file is not a Desktop app client. "
            "Create and download a Desktop app OAuth client."
        )

    return path


def main():
    parser = argparse.ArgumentParser(
        description="Authorize TaskFlow to send email using Gmail API."
    )

    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to the downloaded Desktop OAuth client JSON.",
    )

    args = parser.parse_args()

    credentials_path = validate_credentials_file(
        args.credentials
    )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        scopes=[GMAIL_SEND_SCOPE],
    )

    print("Opening your browser for Gmail authorization...")

    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. "
            "Revoke the existing TaskFlow authorization "
            "and run this script again."
        )

    print("\nAuthorization successful.")
    print("\nAdd the following value to your environment:")
    print("GMAIL_REFRESH_TOKEN=")
    print(credentials.refresh_token)

    print(
        "\nKeep this token private. "
        "Never commit it to source control."
    )


if __name__ == "__main__":
    main()
