
from django.conf import settings
from django.db import migrations


def create_verified_profiles(apps, schema_editor):
    AccountProfile = apps.get_model(
        "accounts",
        "AccountProfile",
    )

    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)

    database = schema_editor.connection.alias

    existing_user_ids = (
        User._base_manager.using(database)
        .values_list("pk", flat=True)
        .iterator()
    )

    profiles = (
        AccountProfile(
            user_id=user_id,
            email_verified=True,
        )
        for user_id in existing_user_ids
    )

    AccountProfile.objects.using(database).bulk_create(
        profiles,
        batch_size=1000,
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            create_verified_profiles,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
