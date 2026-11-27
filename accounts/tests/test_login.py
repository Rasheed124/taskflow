
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import AccountProfile


User = get_user_model()


class LoginTests(TestCase):

    def setUp(self):
        self.login_url = reverse("accounts:login")

        self.password = "StrongPassword123!"

    def create_user(self, username, email, verified):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=self.password,
        )

        AccountProfile.objects.create(
            user=user,
            email_verified=verified,
        )

        return user

    def test_login_page_loads(self):
        response = self.client.get(self.login_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/login.html",
        )

    def test_verified_user_can_login(self):
        self.create_user(
            "verified",
            "verified@example.com",
            True,
        )

        response = self.client.post(
            self.login_url,
            {
                "username": "verified",
                "password": self.password,
            },
        )

        self.assertRedirects(
            response,
            reverse("tasks:list"),
        )

    def test_verified_user_can_login_with_email_case_insensitively(self):
        self.create_user("emailuser", "person@example.com", True)

        response = self.client.post(
            self.login_url,
            {
                "username": "PERSON@EXAMPLE.COM",
                "password": self.password,
            },
        )

        self.assertRedirects(response, reverse("tasks:list"))

    def test_duplicate_email_identifiers_fail_closed(self):
        self.create_user("firstduplicate", "shared@example.com", True)
        self.create_user("secondduplicate", "shared@example.com", True)

        response = self.client.post(
            self.login_url,
            {"username": "shared@example.com", "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unregistered_email_gets_account_not_found_message(self):
        response = self.client.post(
            self.login_url,
            {"username": "missing@example.com", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "No account is registered with this email address.",
        )

    def test_registered_email_with_wrong_password_gets_credentials_error(self):
        self.create_user("knownuser", "known@example.com", True)

        response = self.client.post(
            self.login_url,
            {"username": "known@example.com", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password.")
        self.assertNotContains(response, "No account is registered")

    def test_unknown_username_keeps_generic_credentials_error(self):
        response = self.client.post(
            self.login_url,
            {"username": "not-registered", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password.")

    def test_login_preserves_safe_next_destination(self):
        self.create_user("nextuser", "next@example.com", True)
        next_url = reverse("tasks:create")

        response = self.client.post(
            self.login_url,
            {
                "username": "nextuser",
                "password": self.password,
                "next": next_url,
            },
        )

        self.assertRedirects(response, next_url)

    def test_login_rejects_external_next_destination(self):
        self.create_user("safeuser", "safe@example.com", True)

        response = self.client.post(
            self.login_url,
            {
                "username": "safeuser",
                "password": self.password,
                "next": "https://attacker.example/",
            },
        )

        self.assertRedirects(response, reverse("tasks:list"))

    def test_unverified_user_cannot_login(self):
        self.create_user(
            "unverified",
            "unverified@example.com",
            False,
        )

        response = self.client.post(
            self.login_url,
            {
                "username": "unverified",
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account needs email verification.")
        self.assertContains(response, reverse("accounts:resend_email_verification"))

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

    def test_missing_profile_does_not_grant_login(self):
        user = User.objects.create_user(
            username="missingprofile",
            email="missing@example.com",
            password=self.password,
        )

        response = self.client.post(
            self.login_url,
            {
                "username": user.username,
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)

        user_profile = AccountProfile.objects.get(user=user)
        self.assertFalse(user_profile.email_verified)

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

    def test_logout_requires_post(self):
        user = self.create_user(
            "logoutuser",
            "logout@example.com",
            True,
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse("accounts:logout")
        )

        self.assertEqual(response.status_code, 405)

    def test_logout_ends_session(self):
        user = self.create_user(
            "logoutuser",
            "logout@example.com",
            True,
        )

        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:logout")
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )
