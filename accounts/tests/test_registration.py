
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.test import override_settings



from accounts.models import AccountProfile


User = get_user_model()


@override_settings(
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        },
    }
)

class RegistrationTests(TestCase):

    def setUp(self):
        self.register_url = reverse("accounts:register")

    def registration_data(self):
        return {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "StrongPassword123!",
            "password2": "StrongPassword123!",
        }

    def test_registration_page_loads(self):
        response = self.client.get(self.register_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/register.html",
        )

    def test_invalid_registration_preserves_non_sensitive_values(self):
        data = self.registration_data()
        data["password1"] = ""
        data["password2"] = ""

        response = self.client.post(self.register_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="newuser"')
        self.assertContains(response, 'value="newuser@example.com"')
        self.assertNotContains(response, 'value="StrongPassword123!"')

    def test_registration_creates_unverified_user(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(),
        )

        self.assertRedirects(
            response,
            reverse("accounts:email_verification_sent"),
        )

        user = User.objects.get(username="newuser")
        profile = AccountProfile.objects.get(user=user)

        self.assertEqual(user.email, "newuser@example.com")
        self.assertFalse(profile.email_verified)
        self.assertEqual(profile.pending_email, "")

    def test_registration_sends_verification_email(self):
        self.client.post(
            self.register_url,
            self.registration_data(),
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["newuser@example.com"],
        )
        self.assertIn(
            "Verify your TaskFlow email address",
            mail.outbox[0].subject,
        )

    def test_duplicate_email_shows_field_error_without_sending_email(self):
        User.objects.create_user(
            username="existing",
            email="newuser@example.com",
            password="StrongPassword123!",
        )

        response = self.client.post(
            self.register_url,
            self.registration_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertContains(response, "An account already uses this email address.")
        self.assertFalse(
            User.objects.filter(username="newuser").exists()
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_username_shows_field_error_without_sending_email(self):
        User.objects.create_user(
            username="newuser",
            email="another@example.com",
            password="StrongPassword123!",
        )

        response = self.client.post(
            self.register_url,
            self.registration_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertContains(response, "This username is already in use.")
        self.assertEqual(User.objects.filter(username="newuser").count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_identifiers_show_errors_on_both_fields(self):
        User.objects.create_user(
            username="newuser",
            email="newuser@example.com",
            password="StrongPassword123!",
        )

        response = self.client.post(self.register_url, self.registration_data())

        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(len(mail.outbox), 0)

    def test_authenticated_user_cannot_register_again(self):
        user = User.objects.create_user(
            username="loggedin",
            email="loggedin@example.com",
            password="StrongPassword123!",
        )

        self.client.force_login(user)

        response = self.client.get(self.register_url)

        self.assertRedirects(
            response,
            reverse("tasks:list"),
        )
