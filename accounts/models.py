


from django.conf import settings
from django.db import models


class AccountProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_profile",
    )

    email_verified = models.BooleanField(default=False)

    pending_email = models.EmailField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.username}"


class AuthRateLimitBucket(models.Model):
    """Shared request counters for authentication abuse controls."""

    key = models.CharField(max_length=64, unique=True)
    window_started_at = models.DateTimeField(db_index=True)
    request_count = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    violation_count = models.PositiveIntegerField(default=0)
    last_violation_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Auth rate limit: {self.key[:12]}"
