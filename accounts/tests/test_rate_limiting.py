from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.rate_limiting import _consume


class RateLimitRequestTests(TestCase):

    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
    )
    def test_admin_login_is_throttled(self):
        url = reverse("admin:login")
        data = {"username": "unknown-admin", "password": "wrong-password"}

        for _ in range(5):
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 200)

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "60")
        self.assertTemplateUsed(response, "admin/login.html")

    def test_registration_is_throttled_by_email_and_returns_retry_after(self):
        url = reverse("accounts:register")
        data = {
            "username": "rateuser",
            "email": "rate@example.com",
            "password1": "",
            "password2": "",
        }

        for _ in range(3):
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 200)

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 429)
        self.assertGreaterEqual(int(response["Retry-After"]), 60)
        self.assertFalse(response.has_header("Location"))
        self.assertTemplateUsed(response, "accounts/register.html")
        self.assertContains(
            response,
            "Too many attempts",
            status_code=429,
        )

    def test_progressive_cooldown_increases_after_repeated_abuse(self):
        now = timezone.now()
        key = "progressive-cooldown-test"

        self.assertEqual(_consume(key, 1, 60, now), (True, 0))
        self.assertEqual(_consume(key, 1, 60, now)[0], False)
        first_retry = _consume(
            key,
            1,
            60,
            now + timedelta(seconds=1),
        )[1]
        self.assertGreaterEqual(first_retry, 120)


@skipUnless(
    connection.vendor == "postgresql",
    "Row-lock concurrency coverage requires PostgreSQL.",
)
class RateLimitConcurrencyTests(TransactionTestCase):

    reset_sequences = True

    def test_concurrent_requests_cannot_exceed_the_bucket_limit(self):
        key = "concurrent-rate-limit-test"
        now = timezone.now()
        _consume(key, limit=5, window_seconds=60, now=now)
        barrier = Barrier(12)

        def consume_one():
            connections.close_all()
            barrier.wait()
            try:
                return _consume(
                    key,
                    limit=5,
                    window_seconds=60,
                    now=now,
                )[0]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(lambda _: consume_one(), range(12)))

        self.assertEqual(sum(results), 4)
