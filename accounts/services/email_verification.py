from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

from accounts.models import AccountProfile


VERIFICATION_TOKEN_SALT = "accounts.email-verification"
VERIFICATION_TOKEN_MAX_AGE = 60 * 60 * 24


def create_unverified_profile(user):
    """
    Create an unverified account profile for a new user.
    """
    return AccountProfile.objects.create(
        user=user,
        email_verified=False,
    )


def get_account_profile(user):
    """
    Retrieve an account profile.

    Missing profiles are created as unverified.
    Existing accounts are handled by the legacy-account migration.
    """
    profile, _ = AccountProfile.objects.get_or_create(
        user=user,
        defaults={
            "email_verified": False,
        },
    )

    return profile


def generate_verification_token(user, email):
    """
    Generate a signed token containing the user ID
    and normalized email address being verified.
    """
    normalized_email = email.strip().lower()

    return signing.dumps(
        {
            "user_id": user.pk,
            "email": normalized_email,
        },
        salt=VERIFICATION_TOKEN_SALT,
    )


def verify_email_token(token):
    """
    Validate a signed verification token.

    Returns the validated payload or None when the token
    is invalid, expired, or has an unexpected structure.
    """
    payload, _reason = verify_email_token_result(token)
    return payload


def verify_email_token_result(token):
    """Return a payload and a stable reason for expired or malformed links."""
    if not isinstance(token, str) or not token:
        return None, "invalid"

    try:
        payload = signing.loads(
            token,
            salt=VERIFICATION_TOKEN_SALT,
            max_age=VERIFICATION_TOKEN_MAX_AGE,
        )

    except signing.SignatureExpired:
        return None, "expired"

    except signing.BadSignature:
        return None, "invalid"

    if not isinstance(payload, dict):
        return None, "invalid"

    user_id = payload.get("user_id")
    email = payload.get("email")

    if user_id is None or not isinstance(email, str):
        return None, "invalid"

    if not email.strip():
        return None, "invalid"

    return payload, "valid"


def build_verification_url(request, user, email):
    """
    Generate the absolute verification URL.
    """
    token = generate_verification_token(user, email)

    verification_path = reverse(
        "accounts:verify_email",
        kwargs={
            "token": token,
        },
    )

    return request.build_absolute_uri(verification_path)


def send_email_verification(request, user, email):
    """
    Generate and send an email verification link.
    """
    normalized_email = email.strip().lower()

    verification_url = build_verification_url(
        request,
        user,
        normalized_email,
    )

    message = (
        f"Hello {user.username},\n\n"
        "Please verify your TaskFlow email address using this link:\n\n"
        f"{verification_url}\n\n"
        "This verification link expires in 24 hours.\n\n"
        "If you did not request this, you can ignore this email."
    )

    return send_mail(
        subject="Verify your TaskFlow email address",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[normalized_email],
        fail_silently=False,
    )
