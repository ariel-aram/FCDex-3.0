from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcdex_3_0", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="scheduled_start_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Planned start — registration closes after this time until /tournament start is run.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tournament",
            name="scheduled_end_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Planned end — no new joins or score updates after this time.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="ended_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Actual time the tournament was completed via /tournament advance.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="started_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Actual time the group stage was started via /tournament start.",
                null=True,
            ),
        ),
    ]
