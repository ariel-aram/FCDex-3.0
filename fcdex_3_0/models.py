from __future__ import annotations

from django.db import models

from bd_models.models import Ball, BallInstance, Player


class TournamentGroup(models.TextChoices):
    LEGACY = "legacy", "Legacy"
    MAIN = "main", "Main"


class TournamentStatus(models.TextChoices):
    REGISTRATION = "registration", "Registration"
    GROUP_STAGE = "group_stage", "Group Stage"
    SEMIFINALS = "semifinals", "Semifinals"
    FINALS = "finals", "Finals"
    COMPLETED = "completed", "Completed"


class TournamentRound(models.TextChoices):
    GROUP = "group", "Group"
    SEMIFINAL = "semifinal", "Semifinal"
    FINAL = "final", "Final"


class AchievementType(models.TextChoices):
    BATTLES_WON = "battles_won", "Battles Won"
    MERGES = "merges", "Merges Completed"
    TOURNAMENT_WIN = "tournament_win", "Tournament Wins"
    TOURNAMENT_PARTICIPATE = "tournament_participate", "Tournament Participation"
    BALLS_OWNED = "balls_owned", "Clubballs Owned"
    CUSTOM = "custom", "Custom (manual)"


class PlayerStats(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="fcdex_stats")
    player_id: int
    battles_won = models.PositiveIntegerField(default=0)
    battles_played = models.PositiveIntegerField(default=0)
    merges_completed = models.PositiveIntegerField(default=0)
    tournament_wins = models.PositiveIntegerField(default=0)
    tournament_participations = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "FCDex player stats"
        verbose_name_plural = "FCDex player stats"

    def __str__(self) -> str:
        return f"Stats for player #{self.player_id}"


class Achievement(models.Model):
    name = models.CharField(max_length=64, unique=True)
    description = models.TextField()
    emoji = models.CharField(max_length=32, default="🏆")
    achievement_type = models.CharField(max_length=32, choices=AchievementType.choices)
    required_count = models.PositiveIntegerField(default=1)
    reward_money = models.PositiveBigIntegerField(default=0)
    reward_ball = models.ForeignKey(Ball, on_delete=models.SET_NULL, null=True, blank=True)
    reward_ball_id: int | None
    hidden = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class PlayerAchievement(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="fcdex_achievements")
    player_id: int
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    progress = models.PositiveIntegerField(default=0)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("player", "achievement")

    def __str__(self) -> str:
        return f"{self.player_id} - {self.achievement.name}"


class Tournament(models.Model):
    name = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, default="")
    host = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="hosted_tournaments")
    host_id: int
    status = models.CharField(max_length=16, choices=TournamentStatus.choices, default=TournamentStatus.REGISTRATION)
    semifinal_cutoff = models.PositiveIntegerField(
        default=0, help_text="Minimum group score required to reach semifinals. Lowest scorers are eliminated."
    )
    match_win_reward = models.PositiveIntegerField(
        default=500, help_text="Fallback coins when no bounty pool is configured on the match."
    )
    rules = models.TextField(
        blank=True, default="", help_text="Tournament rules shown in /tournament view and /tournament rules."
    )
    betting_enabled = models.BooleanField(default=True)
    min_bet = models.PositiveIntegerField(default=100)
    max_bet = models.PositiveIntegerField(default=50_000)
    bet_payout_multiplier = models.PositiveSmallIntegerField(
        default=2, help_text="Multiplier applied to winning bets (e.g. 2 = double your wager)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_start_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Planned start — registration closes after this time until /tournament start is run.",
    )
    scheduled_end_at = models.DateTimeField(
        null=True, blank=True, help_text="Planned end — no new joins or score updates after this time."
    )
    started_at = models.DateTimeField(
        null=True, blank=True, help_text="Actual time the group stage was started via /tournament start."
    )
    ended_at = models.DateTimeField(
        null=True, blank=True, help_text="Actual time the tournament was completed via /tournament advance."
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name


class TournamentRegistration(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="registrations")
    tournament_id: int
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="tournament_registrations")
    player_id: int
    group = models.CharField(max_length=8, choices=TournamentGroup.choices)
    score = models.IntegerField(default=0)
    eliminated = models.BooleanField(default=False)
    semifinal_eligible = models.BooleanField(default=True)

    class Meta:
        unique_together = ("tournament", "player")

    def __str__(self) -> str:
        return f"{self.player_id} in tournament #{self.tournament_id} ({self.group})"


class TournamentMatch(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="matches")
    tournament_id: int
    round = models.CharField(max_length=12, choices=TournamentRound.choices)
    group = models.CharField(max_length=8, choices=TournamentGroup.choices, null=True, blank=True)
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="tournament_matches_as_p1")
    player2 = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="tournament_matches_as_p2", null=True, blank=True
    )
    winner = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name="tournament_wins")
    score1 = models.IntegerField(default=0)
    score2 = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    reward_claimed = models.BooleanField(default=False)
    verified_winner = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_tournament_match_wins",
        help_text="Set when a linked /battle between the two players finishes.",
    )
    verified_winner_id: int | None
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.tournament_id} - {self.round} #{self.pk}"


class TournamentPrizeType(models.TextChoices):
    COINS = "coins", "Coins"
    RANDOM_COMMON = "random_common", "Random Common Clubball"
    BALL = "ball", "Specific Clubball"


class TournamentMatchPrize(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="prizes")
    tournament_id: int
    match = models.ForeignKey(
        TournamentMatch,
        on_delete=models.CASCADE,
        related_name="prizes",
        null=True,
        blank=True,
        help_text="Leave empty to apply this bounty to every match in the round/group.",
    )
    match_id: int | None
    round = models.CharField(max_length=12, choices=TournamentRound.choices)
    group = models.CharField(max_length=8, choices=TournamentGroup.choices, null=True, blank=True)
    prize_type = models.CharField(max_length=16, choices=TournamentPrizeType.choices)
    coins = models.PositiveIntegerField(default=0)
    ball = models.ForeignKey(Ball, on_delete=models.SET_NULL, null=True, blank=True)
    ball_id: int | None
    weight = models.PositiveIntegerField(default=1)
    label = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ("pk",)

    def __str__(self) -> str:
        target = f"match #{self.match_id}" if self.match_id else f"{self.round}/{self.group or 'all'}"
        return f"{self.tournament_id} · {target} · {self.prize_type}"


class TournamentBet(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="bets")
    tournament_id: int
    match = models.ForeignKey(TournamentMatch, on_delete=models.CASCADE, related_name="bets")
    match_id: int
    bettor = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="tournament_bets")
    bettor_id: int
    picked = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="tournament_bets_picked")
    picked_id: int
    amount = models.PositiveIntegerField()
    payout = models.PositiveIntegerField(default=0)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Bet #{self.pk} · match {self.match_id} · {self.amount} coins"


class MergeLog(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="merge_logs")
    player_id: int
    source_ball1 = models.ForeignKey(BallInstance, on_delete=models.SET_NULL, null=True, related_name="merge_source1")
    source_ball2 = models.ForeignKey(BallInstance, on_delete=models.SET_NULL, null=True, related_name="merge_source2")
    result_ball = models.ForeignKey(BallInstance, on_delete=models.SET_NULL, null=True, related_name="merge_results")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Merge #{self.pk} by player {self.player_id}"
