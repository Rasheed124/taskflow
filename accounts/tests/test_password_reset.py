
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
import time


User = get_user_model()


class PasswordResetTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            password="OldStrongPassword123!",
        )

        self.reset_url = reverse("accounts:password_reset")

    def test_password_reset_page_loads(self):
        response = self.client.get(self.reset_url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "accounts/password_reset.html",
        )

    def test_password_reset_sends_email(self):
        response = self.client.post(
            self.reset_url,
            {"email": "reset@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
        )

        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(
            mail.outbox[0].to,
            ["reset@example.com"],
        )

    def test_unknown_email_does_not_reveal_account_existence(self):
        response = self.client.post(
            self.reset_url,
            {"email": "unknown@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
        )

        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        MAILERS={
            "default": {
                "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
            },
        }
    )
    def test_known_and_unknown_email_responses_meet_minimum_duration(self):
        durations = []
        for email in ("reset@example.com", "unknown@example.com"):
            started = time.perf_counter()
            response = self.client.post(self.reset_url, {"email": email})
            durations.append(time.perf_counter() - started)
            self.assertRedirects(
                response,
                reverse("accounts:password_reset_done"),
            )

        self.assertGreaterEqual(min(durations), 0.74)

    def test_password_reset_email_contains_reset_link(self):
        self.client.post(
            self.reset_url,
            {"email": "reset@example.com"},
        )

        self.assertEqual(len(mail.outbox), 1)

        self.assertIn(
            "/reset/",
            mail.outbox[0].body,
        )

    def test_user_can_complete_password_reset(self):
        self.client.post(
            self.reset_url,
            {"email": "reset@example.com"},
        )

        self.assertEqual(len(mail.outbox), 1)

        # Extract the reset URL from the email.
        reset_link = next(
            line.strip()
            for line in mail.outbox[0].body.splitlines()
            if "/reset/" in line
        )

        response = self.client.get(reset_link, follow=True)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "accounts/password_reset_confirm.html",
        )

        confirm_url = response.wsgi_request.path

        response = self.client.post(
            confirm_url,
            {
                "new_password1": "NewResetPassword456!",
                "new_password2": "NewResetPassword456!",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_complete"),
        )

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("NewResetPassword456!")
        )




    def test_password_reset_rejects_mismatched_passwords(self):
        self.client.post(
            self.reset_url,
            {"email": "reset@example.com"},
        )

        reset_link = next(
            line.strip()
            for line in mail.outbox[0].body.splitlines()
            if "/reset/" in line
        )

        response = self.client.get(reset_link, follow=True)

        self.assertEqual(response.status_code, 200)

        confirm_url = response.wsgi_request.path

        response = self.client.post(
            confirm_url,
            {
                "new_password1": "NewResetPassword456!",
                "new_password2": "DifferentPassword789!",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("OldStrongPassword123!")
        )
