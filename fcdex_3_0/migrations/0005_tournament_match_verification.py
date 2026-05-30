from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcdex_3_0", "0004_tournament_bounties_bets_rules")]

    operations = [
        migrations.AddField(
            model_name="tournamentmatch", name="verified_at", field=models.DateTimeField(blank=True, null=True)
        ),
        migrations.AddField(
            model_name="tournamentmatch",
            name="verified_winner",
            field=models.ForeignKey(
                blank=True,
                help_text="Set when a linked /battle between the two players finishes.",
                null=True,
                on_delete=models.SET_NULL,
                related_name="verified_tournament_match_wins",
                to="bd_models.player",
            ),
        ),
    ]
