from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from accounts.admin import AccountProfileAdmin
from accounts.models import AccountProfile


User = get_user_model()


class AccountAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="siteadmin",
            email="admin@example.com",
            password="StrongAdminPassword123!",
        )
        self.client.force_login(self.admin_user)

    def create_user(self, username, email, verified=None):
        user = User.objects.create_user(
            username=username,
            email=email,
            password="StrongPassword123!",
        )
        if verified is not None:
            AccountProfile.objects.create(
                user=user,
                email_verified=verified,
            )
        return user

    def test_user_directory_shows_account_status_and_can_search_email(self):
        self.create_user("verifieduser", "verified@example.com", True)
        self.create_user("pendinguser", "pending@example.com", False)

        response = self.client.get(reverse("admin:auth_user_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "verified@example.com")
        self.assertContains(response, "Verified")
        self.assertContains(response, "Not verified")

        search_response = self.client.get(
            reverse("admin:auth_user_changelist"),
            {"q": "pending@example.com"},
        )
        self.assertContains(search_response, "pending@example.com")
        self.assertNotContains(search_response, "verified@example.com")

    def test_verification_filter_includes_legacy_profiles_as_unverified(self):
        verified = self.create_user("verifieduser", "verified@example.com", True)
        unverified = self.create_user("pendinguser", "pending@example.com", False)
        legacy = self.create_user("legacyuser", "legacy@example.com")

        response = self.client.get(
            reverse("admin:auth_user_changelist"),
            {"email_verification": "unverified"},
        )

        visible_ids = {user.pk for user in response.context["cl"].queryset}
        self.assertIn(unverified.pk, visible_ids)
        self.assertIn(legacy.pk, visible_ids)
        self.assertNotIn(verified.pk, visible_ids)

    def test_profile_directory_is_read_only(self):
        user = self.create_user("pendinguser", "pending@example.com", False)
        AccountProfile.objects.filter(user=user).update(
            pending_email="new-address@example.com",
        )

        response = self.client.get(
            reverse("admin:accounts_accountprofile_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "new-address@example.com")
        profile_admin = AccountProfileAdmin(AccountProfile, admin.site)
        request = RequestFactory().get("/admin/accounts/accountprofile/")
        self.assertFalse(profile_admin.has_add_permission(request))
        self.assertFalse(profile_admin.has_change_permission(request))
        self.assertFalse(profile_admin.has_delete_permission(request))

    def test_non_staff_user_cannot_open_admin_directory(self):
        user = self.create_user("regularuser", "regular@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:auth_user_changelist"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])
