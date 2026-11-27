
import base64
from unittest.mock import MagicMock, patch

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase

from accounts.email_backends.gmail_api import (
    EmailBackend,
    GmailAuthenticationError,
)


class GmailAPIBackendTests(SimpleTestCase):
    def setUp(self):
        self.backend = EmailBackend(
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
        )

        self.email = EmailMessage(
            subject="TaskFlow verification",
            body="Please verify your email address.",
            from_email="TaskFlow <taskflow@gmail.com>",
            to=["recipient@example.com"],
        )

    @patch("accounts.email_backends.gmail_api.build")
    @patch("accounts.email_backends.gmail_api.Request")
    @patch("accounts.email_backends.gmail_api.Credentials")
    def test_sends_email_through_gmail_api(
        self,
        credentials_class,
        request_class,
        build,
    ):
        service = MagicMock()

        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "gmail-message-id",
        }

        build.return_value = service

        result = self.backend.send_messages([self.email])

        self.assertEqual(result, 1)

        credentials_class.assert_called_once()
        credentials_class.return_value.refresh.assert_called_once()

        build.assert_called_once_with(
            "gmail",
            "v1",
            credentials=credentials_class.return_value,
            cache_discovery=False,
        )

        send_method = (
            service.users.return_value
            .messages.return_value.send
        )

        send_method.assert_called_once()

        call_kwargs = send_method.call_args.kwargs

        self.assertEqual(call_kwargs["userId"], "me")

        raw_message = call_kwargs["body"]["raw"]

        decoded_message = base64.urlsafe_b64decode(
            raw_message
        )

        self.assertIn(
            b"TaskFlow verification",
            decoded_message,
        )

        self.assertIn(
            b"recipient@example.com",
            decoded_message,
        )

    def test_empty_message_list_returns_zero(self):
        result = self.backend.send_messages([])

        self.assertEqual(result, 0)

    def test_message_without_recipients_is_skipped(self):
        email = EmailMessage(
            subject="No recipient",
            body="Test",
            from_email="taskflow@gmail.com",
            to=[],
        )

        result = self.backend.send_messages([email])

        self.assertEqual(result, 0)

    @patch("accounts.email_backends.gmail_api.build")
    @patch("accounts.email_backends.gmail_api.Request")
    @patch("accounts.email_backends.gmail_api.Credentials")
    def test_gmail_service_is_reused(
        self,
        credentials_class,
        request_class,
        build,
    ):
        service = MagicMock()

        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "message-id",
        }

        build.return_value = service

        self.backend._get_service()
        self.backend._get_service()

        build.assert_called_once()

    @patch("accounts.email_backends.gmail_api.build")
    @patch("accounts.email_backends.gmail_api.Request")
    @patch("accounts.email_backends.gmail_api.Credentials")
    def test_api_failure_is_propagated(
        self,
        credentials_class,
        request_class,
        build,
    ):
        service = MagicMock()

        service.users.return_value.messages.return_value.send.return_value.execute.side_effect = (
            RuntimeError("Gmail API unavailable")
        )

        build.return_value = service

        with self.assertLogs(
            "accounts.email_backends.gmail_api",
            level="ERROR",
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Gmail API unavailable",
            ):
                self.backend.send_messages([self.email])

    @patch("accounts.email_backends.gmail_api.build")
    @patch("accounts.email_backends.gmail_api.Request")
    @patch("accounts.email_backends.gmail_api.Credentials")
    def test_fail_silently_returns_zero(
        self,
        credentials_class,
        request_class,
        build,
    ):
        backend = EmailBackend(
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
            fail_silently=True,
        )

        build.side_effect = RuntimeError(
            "Gmail API unavailable"
        )

        with self.assertLogs(
            "accounts.email_backends.gmail_api",
            level="ERROR",
        ):
            result = backend.send_messages([self.email])

        self.assertEqual(result, 0)

    def test_backend_accepts_django_mailer_alias(self):
        backend = EmailBackend(
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
            alias="default",
        )

        self.assertEqual(backend.alias, "default")

    def test_missing_credentials_are_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Missing Gmail API credentials",
        ):
            EmailBackend(
                client_id="",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token",
            )

    @patch("accounts.email_backends.gmail_api.Request")
    @patch("accounts.email_backends.gmail_api.Credentials")
    def test_refresh_token_failure_is_reported(
        self,
        credentials_class,
        request_class,
    ):
        from google.auth.exceptions import RefreshError

        credentials_class.return_value.refresh.side_effect = (
            RefreshError("invalid_grant")
        )

        with self.assertLogs(
            "accounts.email_backends.gmail_api",
            level="ERROR",
        ):
            with self.assertRaises(GmailAuthenticationError):
                self.backend._get_credentials()

    @patch("accounts.email_backends.gmail_api.build")
    @patch("accounts.email_backends.gmail_api.Request")
    @patch("accounts.email_backends.gmail_api.Credentials")
    def test_html_alternative_is_preserved(
        self,
        credentials_class,
        request_class,
        build,
    ):
        email = EmailMultiAlternatives(
            subject="HTML test",
            body="Plain text version",
            from_email="TaskFlow <taskflow@gmail.com>",
            to=["recipient@example.com"],
        )

        email.attach_alternative(
            "<h1>TaskFlow</h1>",
            "text/html",
        )

        service = MagicMock()

        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "html-message-id",
        }

        build.return_value = service

        self.backend.send_messages([email])

        raw_message = (
            service.users.return_value
            .messages.return_value.send.call_args.kwargs["body"]["raw"]
        )

        decoded_message = base64.urlsafe_b64decode(raw_message)

        self.assertIn(b"text/html", decoded_message)
        self.assertIn(b"TaskFlow", decoded_message)
