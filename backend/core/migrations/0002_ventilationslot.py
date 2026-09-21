import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VentilationSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "co2_limit_ppm",
                    models.PositiveIntegerField(
                        default=1000,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "greenhouse",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ventilation_slots",
                        to="core.greenhouse",
                    ),
                ),
            ],
            options={
                "ordering": ["greenhouse_id", "start_time"],
            },
        ),
    ]
