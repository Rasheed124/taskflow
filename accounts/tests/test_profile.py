
import smtplib
from unittest.mock import patch


from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import AccountProfile


User = get_user_model()


class ProfileViewTests(TestCase):

    def setUp(self):
        self.password = "StrongPassword123!"

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password=self.password,
        )

        self.account_profile = AccountProfile.objects.create(
            user=self.user,
            email_verified=True,
        )

        self.profile_url = reverse("accounts:profile")

        self.client.force_login(self.user)

    def test_profile_requires_authentication(self):
        self.client.logout()

        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response.url,
        )

    def test_authenticated_user_can_view_profile(self):
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "accounts/profile.html",
        )

        self.assertContains(response, "test@example.com")

    @patch("accounts.views.send_email_verification")
    def test_user_can_update_username_and_request_email_change(
        self,
        mock_send_verification,
    ):
        response = self.client.post(
            self.profile_url,
            {
                "username": "updateduser",
                "email": "newemail@example.com",
            },
        )

        # The request must complete through the profile view.
        self.assertRedirects(
            response,
            self.profile_url,
        )

        self.user.refresh_from_db()
        self.account_profile.refresh_from_db()

        # Username is updated.
        self.assertEqual(
            self.user.username,
            "updateduser",
        )

        # The active email must not change before verification.
        self.assertEqual(
            self.user.email,
            "test@example.com",
        )

        # The new email must be persisted as pending.
        self.assertEqual(
            self.account_profile.pending_email,
            "newemail@example.com",
        )

        # The existing verification status is preserved.
        self.assertTrue(
            self.account_profile.email_verified,
        )

        # Verification email must be requested exactly once.
        mock_send_verification.assert_called_once()

        email_service_args = mock_send_verification.call_args.args

        self.assertEqual(
            email_service_args[1].pk,
            self.user.pk,
        )

        self.assertEqual(
            email_service_args[2],
            "newemail@example.com",
        )

    def test_user_can_update_username_without_changing_email(self):
        response = self.client.post(
            self.profile_url,
            {
                "username": "updateduser",
                "email": "test@example.com",
            },
        )

        self.assertRedirects(response, self.profile_url)

        self.user.refresh_from_db()
        self.account_profile.refresh_from_db()

        self.assertEqual(
            self.user.username,
            "updateduser",
        )

        self.assertEqual(
            self.user.email,
            "test@example.com",
        )

        self.assertEqual(
            self.account_profile.pending_email,
            "",
        )

    @patch("accounts.views.send_email_verification")
    def test_user_can_cancel_pending_email_change(
        self,
        mock_send_verification,
    ):
        self.account_profile.pending_email = "pending@example.com"
        self.account_profile.save()

        response = self.client.post(
            self.profile_url,
            {
                "username": "testuser",
                "email": "test@example.com",
            },
        )

        self.assertRedirects(response, self.profile_url)

        self.account_profile.refresh_from_db()

        self.assertEqual(
            self.account_profile.pending_email,
            "",
        )

        mock_send_verification.assert_not_called()

    def test_user_cannot_use_another_users_email(self):
        User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password=self.password,
        )

        response = self.client.post(
            self.profile_url,
            {
                "username": "updateduser",
                "email": "another@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "An account with this email address already exists.",
            response.context["form"].errors["email"],
        )

        self.user.refresh_from_db()
        self.account_profile.refresh_from_db()

        self.assertEqual(
            self.user.username,
            "testuser",
        )

        self.assertEqual(
            self.user.email,
            "test@example.com",
        )

        self.assertEqual(
            self.account_profile.pending_email,
            "",
        )

    def test_user_cannot_use_another_users_pending_email(self):
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password=self.password,
        )

        AccountProfile.objects.create(
            user=another_user,
            email_verified=True,
            pending_email="pending@example.com",
        )

        response = self.client.post(
            self.profile_url,
            {
                "username": "updateduser",
                "email": "pending@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "An account with this email address already exists.",
            response.context["form"].errors["email"],
        )

        self.user.refresh_from_db()
        self.account_profile.refresh_from_db()

        self.assertEqual(
            self.user.username,
            "testuser",
        )

        self.assertEqual(
            self.user.email,
            "test@example.com",
        )

        self.assertEqual(
            self.account_profile.pending_email,
            "",
        )

    def test_invalid_profile_data_does_not_update_user(self):
        response = self.client.post(
            self.profile_url,
            {
                "username": "",
                "email": "invalid-email",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.account_profile.refresh_from_db()

        self.assertEqual(
            self.user.username,
            "testuser",
        )

        self.assertEqual(
            self.user.email,
            "test@example.com",
        )

        self.assertEqual(
            self.account_profile.pending_email,
            "",
        )

    def test_user_can_change_email_case_without_creating_pending_change(self):
        response = self.client.post(
            self.profile_url,
            {
                "username": "testuser",
                "email": "TEST@example.com",
            },
        )

        self.assertRedirects(response, self.profile_url)

        self.account_profile.refresh_from_db()

        self.assertEqual(
            self.account_profile.pending_email,
            "",
        )



    @patch(
        "accounts.views.send_email_verification",
        side_effect=smtplib.SMTPDataError(
            550,
            b"You can only send testing emails to your own email address.",
        ),
    )
    def test_failed_email_delivery_does_not_save_pending_email(
        self,
        mock_send_verification,
    ):
        with self.assertLogs(
            "accounts.views",
            level="ERROR",
        ):
            response = self.client.post(
                self.profile_url,
                {
                    "username": "updateduser",
                    "email": "newemail@example.com",
                },
                follow=True,
            )
        # Confirm that the profile view redirected successfully.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(self.profile_url, 302)],
        )

        self.user.refresh_from_db()
        self.account_profile.refresh_from_db()

        # Username update should still succeed.
        self.assertEqual(
            self.user.username,
            "updateduser",
        )

        # Original email remains active.
        self.assertEqual(
            self.user.email,
            "test@example.com",
        )

        # Failed delivery must not leave a new pending email.
        self.assertEqual(
            self.account_profile.pending_email,
            "",
        )

        # Verify that the email service was called once.
        mock_send_verification.assert_called_once()

        # Verify that the user sees the delivery failure message.
        self.assertContains(
            response,
            "Resend rejected this verification email",
        )
