
from unittest.mock import patch

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase

from accounts.email_backends.resend import EmailBackend


class ResendEmailBackendTests(SimpleTestCase):

    def setUp(self):
        self.backend = EmailBackend(api_key="re_test_api_key")

    @patch("accounts.email_backends.resend.resend.Emails.send")
    def test_sends_plain_text_email(self, mock_send):
        message = EmailMessage(
            subject="Test email",
            body="Hello from TaskFlow",
            from_email="TaskFlow <onboarding@resend.dev>",
            to=["recipient@example.com"],
        )

        result = self.backend.send_messages([message])

        self.assertEqual(result, 1)

        mock_send.assert_called_once()

        params = mock_send.call_args.args[0]

        self.assertEqual(params["subject"], "Test email")
        self.assertEqual(params["text"], "Hello from TaskFlow")
        self.assertEqual(params["to"], ["recipient@example.com"])

    @patch("accounts.email_backends.resend.resend.Emails.send")
    def test_sends_html_email(self, mock_send):
        message = EmailMessage(
            subject="HTML email",
            body="<h1>Welcome to TaskFlow</h1>",
            from_email="TaskFlow <onboarding@resend.dev>",
            to=["recipient@example.com"],
        )

        message.content_subtype = "html"

        result = self.backend.send_messages([message])

        self.assertEqual(result, 1)

        params = mock_send.call_args.args[0]

        self.assertEqual(
            params["html"],
            "<h1>Welcome to TaskFlow</h1>",
        )

    @patch("accounts.email_backends.resend.resend.Emails.send")
    def test_sends_multipart_email(self, mock_send):
        message = EmailMultiAlternatives(
            subject="Multipart email",
            body="Plain text version",
            from_email="TaskFlow <onboarding@resend.dev>",
            to=["recipient@example.com"],
        )

        message.attach_alternative(
            "<h1>HTML version</h1>",
            "text/html",
        )

        result = self.backend.send_messages([message])

        self.assertEqual(result, 1)

        params = mock_send.call_args.args[0]

        self.assertEqual(params["text"], "Plain text version")
        self.assertEqual(params["html"], "<h1>HTML version</h1>")

    @patch("accounts.email_backends.resend.resend.Emails.send")
    def test_supports_cc_bcc_and_reply_to(self, mock_send):
        message = EmailMessage(
            subject="Recipient test",
            body="Testing recipients",
            from_email="TaskFlow <onboarding@resend.dev>",
            to=["recipient@example.com"],
            cc=["copy@example.com"],
            bcc=["hidden@example.com"],
            reply_to=["support@example.com"],
        )

        self.backend.send_messages([message])

        params = mock_send.call_args.args[0]

        self.assertEqual(params["cc"], ["copy@example.com"])
        self.assertEqual(params["bcc"], ["hidden@example.com"])
        self.assertEqual(
            params["reply_to"],
            ["support@example.com"],
        )

    @patch("accounts.email_backends.resend.resend.Emails.send")
    def test_returns_zero_when_no_messages_are_provided(self, mock_send):
        result = self.backend.send_messages([])

        self.assertEqual(result, 0)
        mock_send.assert_not_called()

    @patch("accounts.email_backends.resend.resend.Emails.send")
    def test_raises_error_when_resend_request_fails(self, mock_send):
        mock_send.side_effect = Exception("Resend API error")

        message = EmailMessage(
            subject="Failure test",
            body="Testing failure",
            from_email="TaskFlow <onboarding@resend.dev>",
            to=["recipient@example.com"],
        )

        with self.assertLogs(
            "accounts.email_backends.resend",
            level="ERROR",
        ):
            with self.assertRaisesRegex(Exception, "Resend API error"):
                self.backend.send_messages([message])



    @patch("accounts.email_backends.resend.resend.Emails.send")
    def test_fail_silently_returns_zero_when_request_fails(self, mock_send):
        mock_send.side_effect = Exception("Resend API error")

        backend = EmailBackend(
            api_key="re_test_api_key",
            fail_silently=True,
        )

        message = EmailMessage(
            subject="Silent failure test",
            body="Testing silent failure",
            from_email="TaskFlow <onboarding@resend.dev>",
            to=["recipient@example.com"],
        )

        with self.assertLogs(
            "accounts.email_backends.resend",
            level="ERROR",
        ):
            result = backend.send_messages([message])

        self.assertEqual(result, 0)



    def test_backend_accepts_django_mailer_alias(self):
        backend = EmailBackend(
            api_key="re_test_api_key",
            alias="default",
        )

        self.assertEqual(backend.alias, "default")
        self.assertEqual(backend.api_key, "re_test_api_key")
