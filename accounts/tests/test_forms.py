
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.forms import (
    NormalizedPasswordResetForm,
    ProfileUpdateForm,
    RegistrationForm,
    ResendVerificationForm,
)
from accounts.models import AccountProfile


User = get_user_model()


class RegistrationFormTests(TestCase):

    def test_valid_registration_form(self):
        form = RegistrationForm(
            data={
                "username": "testuser",
                "email": "test@example.com",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_registration_reports_existing_email(self):
        User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="StrongPassword123!",
        )

        form = RegistrationForm(
            data={
                "username": "newuser",
                "email": "existing@example.com",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertTrue(form.has_account_conflict())

    def test_registration_reports_pending_email(self):
        user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="StrongPassword123!",
        )

        AccountProfile.objects.create(
            user=user,
            email_verified=True,
            pending_email="pending@example.com",
        )

        form = RegistrationForm(
            data={
                "username": "newuser",
                "email": "pending@example.com",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertTrue(form.has_account_conflict())

    def test_registration_reports_existing_username(self):
        User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="StrongPassword123!",
        )

        form = RegistrationForm(
            data={
                "username": "existing",
                "email": "new@example.com",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertTrue(form.has_account_conflict())

    def test_registration_uses_friendly_username_character_error(self):
        form = RegistrationForm(
            data={
                "username": "bad username",
                "email": "new@example.com",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["username"],
            ["Use letters, numbers, and @ . + - _ characters only."],
        )

    def test_registration_normalizes_email(self):
        form = RegistrationForm(
            data={
                "username": "newuser",
                "email": " TEST@EXAMPLE.COM ",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["email"],
            "test@example.com",
        )


class ProfileUpdateFormTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="profileuser",
            email="profile@example.com",
            password="StrongPassword123!",
        )

        AccountProfile.objects.create(
            user=self.user,
            email_verified=True,
        )

    def test_valid_profile_update(self):
        form = ProfileUpdateForm(
            data={
                "username": "updateduser",
                "email": "profile@example.com",
            },
            instance=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_profile_uses_friendly_username_character_error(self):
        form = ProfileUpdateForm(
            data={
                "username": "bad username",
                "email": "profile@example.com",
            },
            instance=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["username"],
            ["Use letters, numbers, and @ . + - _ characters only."],
        )

    def test_profile_rejects_another_users_email(self):
        User.objects.create_user(
            username="another",
            email="another@example.com",
            password="StrongPassword123!",
        )

        form = ProfileUpdateForm(
            data={
                "username": "profileuser",
                "email": "another@example.com",
            },
            instance=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_profile_rejects_another_users_pending_email(self):
        another_user = User.objects.create_user(
            username="another",
            email="another@example.com",
            password="StrongPassword123!",
        )

        AccountProfile.objects.create(
            user=another_user,
            email_verified=True,
            pending_email="pending@example.com",
        )

        form = ProfileUpdateForm(
            data={
                "username": "profileuser",
                "email": "pending@example.com",
            },
            instance=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_profile_normalizes_email(self):
        form = ProfileUpdateForm(
            data={
                "username": "profileuser",
                "email": " NEW@EXAMPLE.COM ",
            },
            instance=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["email"],
            "new@example.com",
        )


class ResendVerificationFormTests(TestCase):

    def test_normalizes_email(self):
        form = ResendVerificationForm(
            data={"email": "  VERIFY@EXAMPLE.COM  "}
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["email"],
            "verify@example.com",
        )

    def test_password_reset_form_normalizes_email(self):
        form = NormalizedPasswordResetForm(
            data={"email": "  RESET@EXAMPLE.COM  "}
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["email"],
            "reset@example.com",
        )

    def test_valid_email(self):
        form = ResendVerificationForm(
            data={"email": "test@example.com"}
        )

        self.assertTrue(form.is_valid())

    def test_invalid_email(self):
        form = ResendVerificationForm(
            data={"email": "invalid-email"}
        )

        self.assertFalse(form.is_valid())
