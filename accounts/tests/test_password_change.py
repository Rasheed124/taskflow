
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class PasswordChangeTests(TestCase):

    def setUp(self):
        self.password = "OldStrongPassword123!"

        self.user = User.objects.create_user(
            username="passworduser",
            email="password@example.com",
            password=self.password,
        )

        self.change_url = reverse("accounts:password_change")
        self.done_url = reverse("accounts:password_change_done")

    def test_password_change_requires_authentication(self):
        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response.url,
        )

    def test_password_change_page_loads(self):
        self.client.force_login(self.user)

        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "accounts/password_change.html",
        )

    def test_user_can_change_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.change_url,
            {
                "old_password": self.password,
                "new_password1": "NewStrongPassword456!",
                "new_password2": "NewStrongPassword456!",
            },
        )

        self.assertRedirects(response, self.done_url)

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password("NewStrongPassword456!")
        )

    def test_password_change_rejects_incorrect_old_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.change_url,
            {
                "old_password": "WrongPassword123!",
                "new_password1": "NewStrongPassword456!",
                "new_password2": "NewStrongPassword456!",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password(self.password)
        )

    def test_password_change_rejects_mismatched_passwords(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.change_url,
            {
                "old_password": self.password,
                "new_password1": "NewStrongPassword456!",
                "new_password2": "DifferentPassword789!",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password(self.password)
        )
