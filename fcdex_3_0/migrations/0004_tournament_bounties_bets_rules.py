from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("fcdex_3_0", "0003_tournament_match_rewards")]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="bet_payout_multiplier",
            field=models.PositiveSmallIntegerField(
                default=2, help_text="Multiplier applied to winning bets (e.g. 2 = double your wager)."
            ),
        ),
        migrations.AddField(model_name="tournament", name="betting_enabled", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="tournament", name="max_bet", field=models.PositiveIntegerField(default=50000)),
        migrations.AddField(model_name="tournament", name="min_bet", field=models.PositiveIntegerField(default=100)),
        migrations.AddField(
            model_name="tournament",
            name="rules",
            field=models.TextField(
                blank=True, default="", help_text="Tournament rules shown in /tournament view overview."
            ),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="match_win_reward",
            field=models.PositiveIntegerField(
                default=500, help_text="Fallback coins when no bounty pool is configured on the match."
            ),
        ),
        migrations.CreateModel(
            name="TournamentMatchPrize",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "round",
                    models.CharField(
                        choices=[("group", "Group"), ("semifinal", "Semifinal"), ("final", "Final")], max_length=12
                    ),
                ),
                (
                    "group",
                    models.CharField(
                        blank=True, choices=[("legacy", "Legacy"), ("main", "Main")], max_length=8, null=True
                    ),
                ),
                (
                    "prize_type",
                    models.CharField(
                        choices=[
                            ("coins", "Coins"),
                            ("random_common", "Random Common Clubball"),
                            ("ball", "Specific Clubball"),
                        ],
                        max_length=16,
                    ),
                ),
                ("coins", models.PositiveIntegerField(default=0)),
                ("weight", models.PositiveIntegerField(default=1)),
                ("label", models.CharField(blank=True, default="", max_length=64)),
                ("ball", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to="bd_models.ball")),
                (
                    "match",
                    models.ForeignKey(
                        blank=True,
                        help_text="Leave empty to apply this bounty to every match in the round/group.",
                        null=True,
                        on_delete=models.CASCADE,
                        related_name="prizes",
                        to="fcdex_3_0.tournamentmatch",
                    ),
                ),
                (
                    "tournament",
                    models.ForeignKey(on_delete=models.CASCADE, related_name="prizes", to="fcdex_3_0.tournament"),
                ),
            ],
            options={"ordering": ("pk",)},
        ),
        migrations.CreateModel(
            name="TournamentBet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.PositiveIntegerField()),
                ("payout", models.PositiveIntegerField(default=0)),
                ("resolved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "bettor",
                    models.ForeignKey(on_delete=models.CASCADE, related_name="tournament_bets", to="bd_models.player"),
                ),
                (
                    "match",
                    models.ForeignKey(on_delete=models.CASCADE, related_name="bets", to="fcdex_3_0.tournamentmatch"),
                ),
                (
                    "picked",
                    models.ForeignKey(
                        on_delete=models.CASCADE, related_name="tournament_bets_picked", to="bd_models.player"
                    ),
                ),
                (
                    "tournament",
                    models.ForeignKey(on_delete=models.CASCADE, related_name="bets", to="fcdex_3_0.tournament"),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
