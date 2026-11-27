
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.urls import reverse

from accounts.models import AccountProfile
from accounts.services.email_verification import (
    VERIFICATION_TOKEN_MAX_AGE,
    VERIFICATION_TOKEN_SALT,
    generate_verification_token,
    verify_email_token,
)


User = get_user_model()


class EmailVerificationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="verifyuser",
            email="verify@example.com",
            password="StrongPassword123!",
        )

        self.profile = AccountProfile.objects.create(
            user=self.user,
            email_verified=False,
        )

        self.token = generate_verification_token(
            self.user,
            self.user.email,
        )

        self.verify_url = reverse(
            "accounts:verify_email",
            kwargs={"token": self.token},
        )

    def test_valid_token_returns_payload(self):
        payload = verify_email_token(self.token)

        self.assertEqual(payload["user_id"], self.user.pk)
        self.assertEqual(payload["email"], self.user.email)

    def test_invalid_token_is_rejected(self):
        payload = verify_email_token("invalid-token")

        self.assertIsNone(payload)

    def test_expired_token_is_rejected(self):
        expired_token = signing.dumps(
            {
                "user_id": self.user.pk,
                "email": self.user.email,
            },
            salt=VERIFICATION_TOKEN_SALT,
        )

        with patch(
            "accounts.services.email_verification.VERIFICATION_TOKEN_MAX_AGE",
            -1,
        ):
            self.assertIsNone(
                verify_email_token(expired_token)
            )

    def test_get_displays_confirmation_without_verifying(self):
        response = self.client.get(self.verify_url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "accounts/email_verification_confirm.html",
        )

        self.profile.refresh_from_db()

        self.assertFalse(self.profile.email_verified)

    def test_post_verifies_registration_email(self):
        response = self.client.post(self.verify_url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "accounts/email_verification_complete.html",
        )

        self.profile.refresh_from_db()

        self.assertTrue(self.profile.email_verified)

    def test_reused_registration_token_is_rejected(self):
        first_response = self.client.post(self.verify_url)

        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post(self.verify_url)

        self.assertEqual(second_response.status_code, 410)

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verified)

    def test_token_for_nonexistent_user_is_rejected(self):
        token = signing.dumps(
            {
                "user_id": 999999,
                "email": "missing@example.com",
            },
            salt=VERIFICATION_TOKEN_SALT,
        )

        response = self.client.post(
            reverse(
                "accounts:verify_email",
                kwargs={"token": token},
            )
        )

        self.assertEqual(response.status_code, 410)

    def test_expired_verification_link_returns_gone(self):
        with patch(
            "accounts.services.email_verification.VERIFICATION_TOKEN_MAX_AGE",
            -1,
        ):
            response = self.client.get(self.verify_url)

        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "has expired", status_code=410)

    def test_email_change_verification_updates_email(self):
        self.profile.email_verified = True
        self.profile.pending_email = "new@example.com"
        self.profile.save()

        token = generate_verification_token(
            self.user,
            "new@example.com",
        )

        response = self.client.post(
            reverse(
                "accounts:verify_email",
                kwargs={"token": token},
            )
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.profile.pending_email, "")
        self.assertTrue(self.profile.email_verified)

    def test_email_change_token_is_rejected_when_email_is_in_use(self):
        self.profile.email_verified = True
        self.profile.pending_email = "another@example.com"
        self.profile.save()

        User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="StrongPassword123!",
        )

        token = generate_verification_token(
            self.user,
            "another@example.com",
        )

        response = self.client.post(
            reverse(
                "accounts:verify_email",
                kwargs={"token": token},
            )
        )

        self.assertEqual(response.status_code, 410)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(self.user.email, "verify@example.com")
        self.assertEqual(
            self.profile.pending_email,
            "another@example.com",
        )

    def test_missing_profile_is_handled(self):
        self.profile.delete()

        response = self.client.post(self.verify_url)

        self.assertEqual(response.status_code, 410)

    @patch("accounts.views.send_email_verification")
    def test_registration_verification_can_be_resent(
        self,
        mock_send_verification,
    ):
        response = self.client.post(
            reverse("accounts:resend_email_verification"),
            {"email": "verify@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("accounts:email_verification_sent"),
        )

        mock_send_verification.assert_called_once_with(
            response.wsgi_request,
            self.user,
            self.user.email,
        )

    @patch("accounts.views.send_email_verification")
    def test_pending_email_verification_can_be_resent(
        self,
        mock_send_verification,
    ):
        self.profile.email_verified = True
        self.profile.pending_email = "new@example.com"
        self.profile.save()

        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "accounts:resend_pending_email_verification"
            )
        )

        self.assertRedirects(
            response,
            reverse("accounts:profile"),
        )

        mock_send_verification.assert_called_once_with(
            response.wsgi_request,
            self.user,
            "new@example.com",
        )

    def test_pending_email_resend_requires_authentication(self):
        response = self.client.post(
            reverse(
                "accounts:resend_pending_email_verification"
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response.url,
        )
