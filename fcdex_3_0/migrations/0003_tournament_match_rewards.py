from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcdex_3_0", "0002_tournament_schedule")]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="match_win_reward",
            field=models.PositiveIntegerField(
                default=500, help_text="Coins awarded when a player claims a tournament match victory."
            ),
        ),
        migrations.AddField(
            model_name="tournamentmatch", name="reward_claimed", field=models.BooleanField(default=False)
        ),
    ]
