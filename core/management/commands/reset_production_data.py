import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management import BaseCommand, CommandError, call_command
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.conf import settings

from accounts.models import AccountProfile


CONFIRMATION_PHRASE = "CLEAR_TASKFLOW_PRODUCTION_DATA"


def get_database_vendor():
    return connection.vendor


def get_database_name():
    return connection.settings_dict.get("NAME")


class Command(BaseCommand):
    help = (
        "Clear all production database rows, retain the schema, and create "
        "a fresh superuser."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            required=True,
            help=f"Required exact confirmation phrase: {CONFIRMATION_PHRASE}",
        )

    def handle(self, *args, **options):
        if options["confirm"] != CONFIRMATION_PHRASE:
            raise CommandError(
                "Reset cancelled: the confirmation phrase did not match."
            )

        if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings.production":
            raise CommandError(
                "Reset refused: DJANGO_SETTINGS_MODULE must be "
                "config.settings.production."
            )

        if settings.DEBUG:
            raise CommandError("Reset refused: DEBUG must be False.")

        if get_database_vendor() != "postgresql":
            raise CommandError(
                "Reset refused: the configured database must be PostgreSQL."
            )

        expected_database_name = os.environ.get("PRODUCTION_DB_NAME", "").strip()
        if not expected_database_name:
            raise CommandError(
                "Reset refused: configure the expected production database name."
            )
        if get_database_name() != expected_database_name:
            raise CommandError(
                "Reset refused: the configured database name does not match "
                "PRODUCTION_DB_NAME."
            )

        admin_username = os.environ.get("PRODUCTION_RESET_ADMIN_USERNAME", "").strip()
        admin_email = os.environ.get("PRODUCTION_RESET_ADMIN_EMAIL", "").strip()
        admin_password = os.environ.get("PRODUCTION_RESET_ADMIN_PASSWORD", "")
        if not admin_username or not admin_email or not admin_password:
            raise CommandError(
                "Reset refused: configure the production reset admin "
                "username, email, and password secrets."
            )

        User = get_user_model()
        admin = User(username=admin_username, email=admin_email)
        try:
            validate_password(admin_password, user=admin)
        except ValidationError as error:
            raise CommandError(
                "Reset refused: the reset admin password does not meet "
                "the configured password requirements."
            ) from error

        self.stdout.write(
            self.style.WARNING(
                "Clearing all database rows. The database schema will remain."
            )
        )

        # Keep the truncate and replacement admin in one PostgreSQL
        # transaction, so an admin-creation error rolls the reset back.
        with transaction.atomic(using="default"):
            call_command(
                "flush",
                database="default",
                interactive=False,
                reset_sequences=True,
            )
            admin_user = User._default_manager.db_manager("default").create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password,
            )
            AccountProfile.objects.using("default").create(
                user=admin_user,
                email_verified=True,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Production data was cleared. A fresh superuser was created."
            )
        )
