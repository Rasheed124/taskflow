
import base64
import logging

from django.core.mail.backends.base import BaseEmailBackend

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


logger = logging.getLogger(__name__)

GMAIL_API_NAME = "gmail"
GMAIL_API_VERSION = "v1"

GMAIL_TOKEN_URI = "https://oauth2.googleapis.com/token"

GMAIL_SEND_SCOPE = (
    "https://www.googleapis.com/auth/gmail.send"
)


class GmailAPIError(Exception):
    """Raised when Gmail API email delivery fails."""


class GmailAuthenticationError(GmailAPIError):
    """Raised when Gmail OAuth authentication fails."""


class EmailBackend(BaseEmailBackend):
    """
    Django email backend powered by the Gmail API.

    Uses an OAuth refresh token to send messages through
    the authorized Gmail account.

    Compatible with Django's MAILERS configuration.
    """

    def __init__(
        self,
        *,
        client_id,
        client_secret,
        refresh_token,
        fail_silently=False,
        **kwargs,
    ):
        # Django 6.1 passes the mailer alias through kwargs.
        # BaseEmailBackend owns the alias initialization.
        super().__init__(**kwargs)

        self.fail_silently = fail_silently

        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

        self._service = None

        missing_credentials = [
            name
            for name, value in {
                "GMAIL_CLIENT_ID": client_id,
                "GMAIL_CLIENT_SECRET": client_secret,
                "GMAIL_REFRESH_TOKEN": refresh_token,
            }.items()
            if not value
        ]

        if missing_credentials:
            raise ValueError(
                "Missing Gmail API credentials: "
                + ", ".join(missing_credentials)
            )

    def _get_credentials(self):
        """Build and refresh Gmail OAuth credentials."""

        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri=GMAIL_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=[GMAIL_SEND_SCOPE],
        )

        try:
            credentials.refresh(Request())

        except RefreshError as exc:
            logger.exception(
                "Gmail OAuth token refresh failed."
            )

            raise GmailAuthenticationError(
                "Gmail authorization has expired or been revoked. "
                "Reauthorize the TaskFlow Gmail account."
            ) from exc

        return credentials

    def _get_service(self):
        """Create the authenticated Gmail API service once."""

        if self._service is not None:
            return self._service

        credentials = self._get_credentials()

        self._service = build(
            GMAIL_API_NAME,
            GMAIL_API_VERSION,
            credentials=credentials,
            cache_discovery=False,
        )

        return self._service

    def send_messages(self, email_messages):
        """
        Send a collection of Django email messages.

        Returns the number of messages accepted by Gmail.
        """

        if not email_messages:
            return 0

        sent_count = 0

        for message in email_messages:
            try:
                if self._send(message):
                    sent_count += 1

            except Exception:
                logger.exception(
                    "Gmail API failed to send a message."
                )

                if not self.fail_silently:
                    raise

        return sent_count

    def _send(self, message):
        """Convert a Django message and send it through Gmail."""

        recipients = (
            list(message.to or [])
            + list(message.cc or [])
            + list(message.bcc or [])
        )

        if not recipients:
            logger.warning(
                "Skipping Gmail message without recipients."
            )
            return False

        # Django handles MIME construction, HTML alternatives,
        # attachments, custom headers and recipient headers.
        mime_message = message.message()

        raw_message = base64.urlsafe_b64encode(
            mime_message.as_bytes()
        ).decode("ascii")

        payload = {
            "raw": raw_message,
        }

        try:
            response = (
                self._get_service()
                .users()
                .messages()
                .send(
                    userId="me",
                    body=payload,
                )
                .execute()
            )

        except HttpError as exc:
            logger.exception(
                "Gmail API rejected an email request."
            )

            raise GmailAPIError(
                "Gmail API rejected the email request."
            ) from exc

        message_id = response.get("id")

        if not message_id:
            raise GmailAPIError(
                "Gmail API returned no message identifier."
            )

        logger.info(
            "Gmail API accepted a message. Message ID: %s",
            message_id,
        )

        return True
