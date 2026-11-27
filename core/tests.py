import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.template.loader import get_template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.middleware import ContentSecurityPolicyMiddleware
from accounts.models import AccountProfile


class HomePageTests(TestCase):

    def setUp(self):
        self.home_url = reverse("core:home")

    def test_homepage_returns_successful_response(self):
        response = self.client.get(self.home_url)

        self.assertEqual(response.status_code, 200)

    def test_homepage_uses_correct_template(self):
        response = self.client.get(self.home_url)

        self.assertTemplateUsed(response, "core/home.html")

    def test_homepage_contains_taskflow_branding(self):
        response = self.client.get(self.home_url)

        self.assertContains(response, "TaskFlow")
        self.assertContains(response, "Make room for")

    def test_homepage_contains_registration_link(self):
        response = self.client.get(self.home_url)

        registration_url = reverse("accounts:register")

        self.assertContains(response, registration_url)

    def test_homepage_is_accessible_without_authentication(self):
        response = self.client.get(self.home_url)

        self.assertEqual(response.status_code, 200)




class PublicPageTests(TestCase):
    def test_homepage_loads(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)

    def test_homepage_contains_social_metadata_and_favicon(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, 'property="og:description"')
        self.assertContains(response, 'property="og:url"')
        self.assertContains(response, "core/favicon.svg")

    def test_robots_txt_returns_plain_text_crawl_guidance(self):
        response = self.client.get(reverse("core:robots"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "Disallow: /tasks/")
        self.assertContains(response, "Disallow: /admin/")

    def test_privacy_policy_loads(self):
        response = self.client.get(reverse("core:privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacy Policy")
        self.assertContains(response, "Gmail API")
        self.assertContains(response, "Limited Use")

    def test_terms_of_service_loads(self):
        response = self.client.get(reverse("core:terms"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Terms of Service")

    def test_homepage_links_to_legal_pages(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(
            response,
            reverse("core:privacy"),
        )

        self.assertContains(
            response,
            reverse("core:terms"),
        )

    def test_legal_pages_are_public(self):
        privacy_response = self.client.get(
            reverse("core:privacy")
        )

        terms_response = self.client.get(
            reverse("core:terms")
        )

        self.assertEqual(privacy_response.status_code, 200)
        self.assertEqual(terms_response.status_code, 200)


class SecurityAndErrorPageTests(TestCase):

    @override_settings(
        CONTENT_SECURITY_POLICY="default-src 'self'",
        CONTENT_SECURITY_POLICY_REPORT_ONLY=True,
    )
    def test_csp_report_only_header_is_set(self):
        middleware = ContentSecurityPolicyMiddleware(
            lambda request: HttpResponse("ok")
        )
        response = middleware(RequestFactory().get("/"))

        self.assertEqual(
            response["Content-Security-Policy-Report-Only"],
            "default-src 'self'",
        )
        self.assertFalse(response.has_header("Content-Security-Policy"))

    @override_settings(
        CONTENT_SECURITY_POLICY="default-src 'self'",
        CONTENT_SECURITY_POLICY_REPORT_ONLY=False,
    )
    def test_csp_enforcement_header_can_be_enabled(self):
        middleware = ContentSecurityPolicyMiddleware(
            lambda request: HttpResponse("ok")
        )
        response = middleware(RequestFactory().get("/"))

        self.assertEqual(
            response["Content-Security-Policy"],
            "default-src 'self'",
        )
        self.assertFalse(
            response.has_header("Content-Security-Policy-Report-Only")
        )

    @override_settings(
        SECURE_HSTS_SECONDS=300,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
    )
    def test_security_middleware_sets_hsts_for_https_responses(self):
        middleware = SecurityMiddleware(lambda request: HttpResponse("ok"))
        response = middleware(RequestFactory().get("/", secure=True))

        self.assertEqual(response["Strict-Transport-Security"], "max-age=300")

    def test_csp_report_is_logged_without_logging_report_details(self):
        payload = {
            "csp-report": {
                "violated-directive": "script-src",
                "blocked-uri": "https://blocked.example/secret?email=user@example.com",
            }
        }

        with self.assertLogs("core.security.csp", level="WARNING") as captured:
            response = self.client.post(
                reverse("core:csp-report"),
                data=json.dumps(payload),
                content_type="application/csp-report",
            )

        self.assertEqual(response.status_code, 204)
        self.assertIn("script-src", captured.output[0])
        self.assertIn("blocked.example", captured.output[0])
        self.assertNotIn("user@example.com", captured.output[0])

    def test_csp_report_body_is_size_limited(self):
        response = self.client.post(
            reverse("core:csp-report"),
            data=" " * 16_385,
            content_type="application/csp-report",
        )

        self.assertEqual(response.status_code, 413)

    @override_settings(DEBUG=False)
    def test_unknown_page_uses_branded_404(self):
        response = self.client.get("/page-that-does-not-exist/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Return to TaskFlow", status_code=404)

    def test_all_branded_error_templates_are_available(self):
        for template_name in ("400.html", "403.html", "404.html", "500.html"):
            with self.subTest(template=template_name):
                self.assertIsNotNone(get_template(template_name))


class ProductionDataResetCommandTests(TestCase):
    confirmation = "CLEAR_TASKFLOW_PRODUCTION_DATA"

    def setUp(self):
        self.environment = {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "PRODUCTION_DB_NAME": "taskflow_production",
            "PRODUCTION_RESET_ADMIN_USERNAME": "resetadmin",
            "PRODUCTION_RESET_ADMIN_EMAIL": "resetadmin@example.com",
            "PRODUCTION_RESET_ADMIN_PASSWORD": "AnotherStrongPassword987!",
        }

    def test_wrong_confirmation_refuses_before_database_checks(self):
        with patch.dict(os.environ, self.environment):
            with self.assertRaisesMessage(CommandError, "confirmation phrase"):
                call_command("reset_production_data", confirm="NO")

    @patch("core.management.commands.reset_production_data.call_command")
    def test_non_production_settings_refuse_without_flushing(self, flush):
        environment = {
            **self.environment,
            "DJANGO_SETTINGS_MODULE": "config.settings.development",
        }
        with patch.dict(os.environ, environment), override_settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, "must be"):
                call_command(
                    "reset_production_data",
                    confirm=self.confirmation,
                )

        flush.assert_not_called()

    @patch("core.management.commands.reset_production_data.call_command")
    def test_debug_mode_refuses_without_flushing(self, flush):
        with patch.dict(os.environ, self.environment), override_settings(DEBUG=True):
            with self.assertRaisesMessage(CommandError, "DEBUG must be False"):
                call_command(
                    "reset_production_data",
                    confirm=self.confirmation,
                )

        flush.assert_not_called()

    @patch("core.management.commands.reset_production_data.call_command")
    def test_non_postgresql_database_refuses_without_flushing(self, flush):
        with patch.dict(os.environ, self.environment), override_settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, "must be PostgreSQL"):
                call_command(
                    "reset_production_data",
                    confirm=self.confirmation,
                )

        flush.assert_not_called()

    @patch(
        "core.management.commands.reset_production_data.get_database_vendor",
        return_value="postgresql",
    )
    @patch(
        "core.management.commands.reset_production_data.get_database_name",
        return_value="another_database",
    )
    @patch("core.management.commands.reset_production_data.call_command")
    def test_database_name_mismatch_refuses_before_flush(
        self,
        flush,
        database_name,
        database_vendor,
    ):
        with (
            patch.dict(os.environ, self.environment),
            override_settings(DEBUG=False),
        ):
            with self.assertRaisesMessage(CommandError, "does not match"):
                call_command(
                    "reset_production_data",
                    confirm=self.confirmation,
                )

        flush.assert_not_called()

    @patch(
        "core.management.commands.reset_production_data.get_database_vendor",
        return_value="postgresql",
    )
    @patch(
        "core.management.commands.reset_production_data.get_database_name",
        return_value="taskflow_production",
    )
    @patch("core.management.commands.reset_production_data.call_command")
    def test_missing_replacement_admin_credentials_refuse_before_flush(
        self,
        flush,
        database_name,
        database_vendor,
    ):
        environment = {
            **self.environment,
            "PRODUCTION_RESET_ADMIN_PASSWORD": "",
        }
        with (
            patch.dict(os.environ, environment),
            override_settings(DEBUG=False),
        ):
            with self.assertRaisesMessage(CommandError, "admin username"):
                call_command(
                    "reset_production_data",
                    confirm=self.confirmation,
                )

        flush.assert_not_called()

    @patch(
        "core.management.commands.reset_production_data.get_database_vendor",
        return_value="postgresql",
    )
    @patch(
        "core.management.commands.reset_production_data.get_database_name",
        return_value="taskflow_production",
    )
    @patch("core.management.commands.reset_production_data.call_command")
    def test_invalid_replacement_admin_password_refuses_before_flush(
        self,
        flush,
        database_name,
        database_vendor,
    ):
        environment = {
            **self.environment,
            "PRODUCTION_RESET_ADMIN_PASSWORD": "short",
        }
        with (
            patch.dict(os.environ, environment),
            override_settings(DEBUG=False),
        ):
            with self.assertRaisesMessage(CommandError, "password"):
                call_command(
                    "reset_production_data",
                    confirm=self.confirmation,
                )

        flush.assert_not_called()

    @patch(
        "core.management.commands.reset_production_data.get_database_vendor",
        return_value="postgresql",
    )
    @patch(
        "core.management.commands.reset_production_data.get_database_name",
        return_value="taskflow_production",
    )
    @patch("core.management.commands.reset_production_data.call_command")
    def test_valid_request_flushes_then_creates_replacement_superuser(
        self,
        flush,
        database_name,
        database_vendor,
    ):
        with (
            patch.dict(os.environ, self.environment),
            override_settings(DEBUG=False),
        ):
            call_command(
                "reset_production_data",
                confirm=self.confirmation,
            )

        flush.assert_called_once_with(
            "flush",
            database="default",
            interactive=False,
            reset_sequences=True,
        )
        admin_user = get_user_model().objects.get(username="resetadmin")
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.account_profile.email_verified)
