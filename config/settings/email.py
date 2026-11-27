
from django.core.exceptions import ImproperlyConfigured


def get_email_mailers(env):
    """
    Build the Django MAILERS configuration
    from environment variables.
    """

    provider = (
        env("EMAIL_PROVIDER", default="console")
        .strip()
        .lower()
    )

    # -------------------------------------------------
    # Console backend
    # -------------------------------------------------

    if provider == "console":
        return {
            "default": {
                "BACKEND": (
                    "django.core.mail.backends.console.EmailBackend"
                ),
            },
        }

    # -------------------------------------------------
    # Gmail API backend
    # -------------------------------------------------

    if provider == "gmail_api":
        credentials = {
            "client_id": env(
                "GMAIL_CLIENT_ID",
                default="",
            ).strip(),

            "client_secret": env(
                "GMAIL_CLIENT_SECRET",
                default="",
            ).strip(),

            "refresh_token": env(
                "GMAIL_REFRESH_TOKEN",
                default="",
            ).strip(),
        }

        missing = [
            key
            for key, value in credentials.items()
            if not value
        ]

        if missing:
            raise ImproperlyConfigured(
                "Missing Gmail API environment variables: "
                + ", ".join(
                    f"GMAIL_{key.upper()}"
                    for key in missing
                )
            )

        return {
            "default": {
                "BACKEND": (
                    "accounts.email_backends.gmail_api.EmailBackend"
                ),
                "OPTIONS": {
                    **credentials,
                    "fail_silently": False,
                },
            },
        }

    # -------------------------------------------------
    # Resend HTTP API backend
    # -------------------------------------------------

    if provider == "resend":
        api_key = env(
            "RESEND_API_KEY",
            default="",
        ).strip()

        if not api_key:
            raise ImproperlyConfigured(
                "RESEND_API_KEY is required when using Resend."
            )

        return {
            "default": {
                "BACKEND": (
                    "accounts.email_backends.resend.EmailBackend"
                ),
                "OPTIONS": {
                    "api_key": api_key,
                    "fail_silently": False,
                },
            },
        }

    # -------------------------------------------------
    # Unsupported provider
    # -------------------------------------------------

    raise ImproperlyConfigured(
        f"Unsupported EMAIL_PROVIDER: {provider}"
    )
