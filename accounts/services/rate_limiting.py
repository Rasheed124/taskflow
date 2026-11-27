"""Database-backed throttling for public authentication endpoints."""

from functools import wraps
import hashlib
import hmac
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils import timezone

from accounts.forms import ProfileUpdateForm, RegistrationForm, ResendVerificationForm
from accounts.forms_auth import TaskFlowAuthenticationForm
from accounts.models import AuthRateLimitBucket
from accounts.services.email_verification import get_account_profile


security_logger = logging.getLogger("accounts.security")

POLICIES = {
    "login": {
        "ip_limit": 15,
        "identity_limit": 5,
        "window": 900,
        "identities": ("username",),
    },
    "admin_login": {
        "ip_limit": 10,
        "identity_limit": 5,
        "window": 900,
        "identities": ("username",),
    },
    "register": {
        "ip_limit": 10,
        "identity_limit": 3,
        "window": 3600,
        "identities": ("username", "email"),
    },
    "password_reset": {
        "ip_limit": 10,
        "identity_limit": 3,
        "window": 3600,
        "identities": ("email",),
    },
    "password_reset_confirm": {
        "ip_limit": 10,
        "identity_limit": 1,
        "window": 3600,
        "identities": (),
    },
    "verification_resend": {
        "ip_limit": 10,
        "identity_limit": 3,
        "window": 3600,
        "identities": ("email",),
    },
}
BASE_COOLDOWN_SECONDS = 60
MAX_COOLDOWN_SECONDS = 3600
VIOLATION_DECAY_SECONDS = 86400
PASSWORD_RESET_MIN_RESPONSE_SECONDS = 0.75
REGISTRATION_MIN_RESPONSE_SECONDS = 1.5


def _digest(scope, identity):
    value = f"{scope}:{identity}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), value, hashlib.sha256
    ).hexdigest()


def _cooldown_seconds(violation_count):
    exponent = min(max(violation_count - 1, 0), 6)
    return min(BASE_COOLDOWN_SECONDS * 2**exponent, MAX_COOLDOWN_SECONDS)


def _consume(key, limit, window_seconds, now=None):
    """Atomically consume one slot, returning (allowed, retry_seconds)."""
    now = now or timezone.now()

    # A concurrent first request may win the unique-key insert. Retry by
    # selecting that row under lock; PostgreSQL serializes later updates.
    for _ in range(3):
        try:
            with transaction.atomic():
                bucket = (
                    AuthRateLimitBucket.objects.select_for_update()
                    .filter(key=key)
                    .first()
                )
                if bucket is None:
                    AuthRateLimitBucket.objects.filter(
                        window_started_at__lt=now - timedelta(days=2)
                    ).exclude(blocked_until__gt=now).delete()
                    AuthRateLimitBucket.objects.create(
                        key=key,
                        window_started_at=now,
                        request_count=1,
                    )
                    return True, 0

                if bucket.blocked_until and bucket.blocked_until > now:
                    if (
                        bucket.last_violation_at is None
                        or (now - bucket.last_violation_at).total_seconds()
                        > VIOLATION_DECAY_SECONDS
                    ):
                        bucket.violation_count = 0
                    bucket.violation_count += 1
                    cooldown = _cooldown_seconds(bucket.violation_count)
                    bucket.blocked_until = now + timedelta(seconds=cooldown)
                    bucket.last_violation_at = now
                    bucket.save(
                        update_fields=[
                            "blocked_until",
                            "violation_count",
                            "last_violation_at",
                        ]
                    )
                    return False, max(
                        1, int((bucket.blocked_until - now).total_seconds())
                    )

                window_expired = (
                    now - bucket.window_started_at
                ).total_seconds() >= window_seconds
                if window_expired:
                    bucket.window_started_at = now
                    bucket.request_count = 0
                    bucket.blocked_until = None

                if bucket.request_count < limit:
                    bucket.request_count += 1
                    bucket.save(
                        update_fields=[
                            "window_started_at",
                            "request_count",
                            "blocked_until",
                        ]
                    )
                    return True, 0

                if (
                    bucket.last_violation_at is None
                    or (now - bucket.last_violation_at).total_seconds()
                    > VIOLATION_DECAY_SECONDS
                ):
                    bucket.violation_count = 0
                bucket.violation_count += 1
                cooldown = _cooldown_seconds(bucket.violation_count)
                bucket.blocked_until = now + timedelta(seconds=cooldown)
                bucket.last_violation_at = now
                bucket.save(
                    update_fields=[
                        "window_started_at",
                        "request_count",
                        "blocked_until",
                        "violation_count",
                        "last_violation_at",
                    ]
                )
                return False, cooldown
        except IntegrityError:
            continue

    # Fail closed if repeated concurrent inserts cannot be resolved.
    return False, BASE_COOLDOWN_SECONDS


def consume_endpoint_limits(request, endpoint):
    policy = POLICIES[endpoint]
    ip = request.META.get("REMOTE_ADDR") or "unknown"
    buckets = [(f"{endpoint}:ip", ip)]
    for field in policy["identities"]:
        value = request.POST.get(field, "").strip().casefold()
        if not value and getattr(request, "user", None) is not None:
            if request.user.is_authenticated and field == "email":
                value = request.user.email.strip().casefold()
        if value:
            buckets.append((f"{endpoint}:{field}", value))

    retry_after = 0
    allowed = True
    for scope, identity in buckets:
        slot_allowed, retry = _consume(
            _digest(scope, identity),
            (
                policy["ip_limit"]
                if scope.endswith(":ip")
                else policy["identity_limit"]
            ),
            policy["window"],
        )
        if not slot_allowed:
            allowed = False
            retry_after = max(retry_after, retry)
    return allowed, retry_after


def rate_limit_auth_view(endpoint):
    """Throttle POSTs and return a user-facing 429 when a bucket is full."""

    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            started = time.monotonic()
            normalize_timing = False
            if request.method == "POST":
                allowed, retry_after = consume_endpoint_limits(
                    request, endpoint
                )
                if not allowed:
                    security_logger.warning(
                        "Authentication throttle activated for endpoint=%s",
                        endpoint,
                    )
                    messages.error(
                        request,
                        "Too many attempts. Please wait before trying again.",
                    )
                    if endpoint == "register":
                        template = "accounts/register.html"
                        form = RegistrationForm()
                        context = {"form": form}
                    elif endpoint == "login":
                        template = "accounts/login.html"
                        context = {
                            "form": TaskFlowAuthenticationForm(request)
                        }
                    elif endpoint == "admin_login":
                        from django.contrib.admin.forms import AdminAuthenticationForm

                        admin_site = view.__self__
                        template = admin_site.login_template or "admin/login.html"
                        context = admin_site.each_context(request)
                        context.update(
                            {
                                "title": "Log in",
                                "app_path": request.get_full_path(),
                                "username": request.POST.get("username", ""),
                                "form": AdminAuthenticationForm(
                                    request,
                                    data=request.POST,
                                ),
                            }
                        )
                    elif endpoint in (
                        "password_reset",
                        "password_reset_confirm",
                    ):
                        template = "accounts/password_reset.html"
                        context = {"form": PasswordResetForm()}
                    elif request.resolver_match.url_name == (
                        "resend_pending_email_verification"
                    ):
                        template = "accounts/profile.html"
                        context = {
                            "form": ProfileUpdateForm(instance=request.user),
                            "account_profile": get_account_profile(
                                request.user
                            ),
                        }
                    else:
                        template = "accounts/email_verification_resend.html"
                        context = {"form": ResendVerificationForm()}
                    response = render(
                        request,
                        template,
                        context,
                        status=429,
                    )
                    response["Retry-After"] = str(retry_after)
                else:
                    normalize_timing = True
                    response = view(request, *args, **kwargs)
                    if endpoint in ("login", "admin_login") and request.user.is_authenticated:
                        username = request.POST.get(
                            "username", ""
                        ).strip().casefold()
                        if username:
                            scope = (
                                "login:username"
                                if endpoint == "login"
                                else "admin_login:username"
                            )
                            AuthRateLimitBucket.objects.filter(
                                key=_digest(scope, username)
                            ).delete()
            else:
                response = view(request, *args, **kwargs)

            minimum = 0
            if normalize_timing and endpoint == "password_reset":
                minimum = PASSWORD_RESET_MIN_RESPONSE_SECONDS
            elif normalize_timing and endpoint == "register":
                minimum = REGISTRATION_MIN_RESPONSE_SECONDS
            if minimum:
                remaining = minimum - (
                    time.monotonic() - started
                )
                if remaining > 0:
                    time.sleep(remaining)
            return response

        return wrapped

    return decorate


