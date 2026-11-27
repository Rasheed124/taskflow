from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_backfill_account_profiles"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthRateLimitBucket",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.CharField(max_length=64, unique=True)),
                ("window_started_at", models.DateTimeField(db_index=True)),
                ("request_count", models.PositiveIntegerField(default=0)),
                (
                    "blocked_until",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("violation_count", models.PositiveIntegerField(default=0)),
                (
                    "last_violation_at",
                    models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]
