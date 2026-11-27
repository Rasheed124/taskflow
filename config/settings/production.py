
from .base import *
from .email import get_email_mailers
from core.security import DEFAULT_CONTENT_SECURITY_POLICY


DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[],
)



DATABASES = {
    "default": env.db("DATABASE_URL"),
}

DATABASES["default"]["CONN_MAX_AGE"] = 600



MIDDLEWARE.insert(
    1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
MIDDLEWARE.insert(
    2,
    "core.middleware.ContentSecurityPolicyMiddleware",
)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}



# HTTPS and secure cookies
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS",
    default=31_536_000,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

CONTENT_SECURITY_POLICY = DEFAULT_CONTENT_SECURITY_POLICY
CONTENT_SECURITY_POLICY_REPORT_ONLY = env.bool(
    "CSP_REPORT_ONLY",
    default=True,
)




# Production logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "core.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


MAILERS = get_email_mailers(env)


DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
