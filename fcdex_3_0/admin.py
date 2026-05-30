from django.contrib import admin

from .models import (
    Achievement,
    MergeLog,
    PlayerAchievement,
    PlayerStats,
    Tournament,
    TournamentBet,
    TournamentMatch,
    TournamentMatchPrize,
    TournamentRegistration,
)


@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    autocomplete_fields = ("player",)
    list_display = ("player", "battles_won", "battles_played", "merges_completed", "tournament_wins")


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    autocomplete_fields = ("reward_ball",)
    list_display = ("name", "achievement_type", "required_count", "reward_money", "enabled", "hidden")
    list_filter = ("achievement_type", "enabled", "hidden")
    search_fields = ("name", "description")


@admin.register(PlayerAchievement)
class PlayerAchievementAdmin(admin.ModelAdmin):
    autocomplete_fields = ("player", "achievement")
    list_display = ("player", "achievement", "progress", "unlocked_at", "claimed_at")
    list_filter = ("achievement",)


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    autocomplete_fields = ("host",)
    list_display = (
        "name",
        "status",
        "host",
        "betting_enabled",
        "scheduled_start_at",
        "scheduled_end_at",
        "semifinal_cutoff",
        "match_win_reward",
        "created_at",
    )
    list_filter = ("status", "betting_enabled")
    search_fields = ("name", "description", "rules")
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {"fields": ("name", "description", "rules", "host", "status", "semifinal_cutoff", "match_win_reward")}),
        ("Betting", {"fields": ("betting_enabled", "min_bet", "max_bet", "bet_payout_multiplier")}),
        (
            "Schedule",
            {
                "fields": ("scheduled_start_at", "scheduled_end_at", "started_at", "ended_at", "created_at"),
                "description": (
                    "Scheduled dates control registration and activity windows. "
                    "Started/ended are set automatically when hosts run /tournament start and /tournament advance."
                ),
            },
        ),
    )


@admin.register(TournamentRegistration)
class TournamentRegistrationAdmin(admin.ModelAdmin):
    autocomplete_fields = ("tournament", "player")
    list_display = ("tournament", "player", "group", "score", "eliminated", "semifinal_eligible")
    list_filter = ("group", "eliminated", "tournament")


@admin.register(TournamentMatch)
class TournamentMatchAdmin(admin.ModelAdmin):
    autocomplete_fields = ("tournament", "player1", "player2", "winner", "verified_winner")
    list_display = (
        "tournament",
        "round",
        "group",
        "player1",
        "player2",
        "winner",
        "completed",
        "verified_winner",
        "reward_claimed",
    )
    list_filter = ("round", "group", "completed", "tournament")


@admin.register(TournamentMatchPrize)
class TournamentMatchPrizeAdmin(admin.ModelAdmin):
    autocomplete_fields = ("tournament", "match", "ball")
    list_display = ("tournament", "match", "round", "group", "prize_type", "coins", "label", "weight")
    list_filter = ("prize_type", "round", "group", "tournament")


@admin.register(TournamentBet)
class TournamentBetAdmin(admin.ModelAdmin):
    autocomplete_fields = ("tournament", "match", "bettor", "picked")
    list_display = ("tournament", "match", "bettor", "picked", "amount", "payout", "resolved", "created_at")
    list_filter = ("resolved", "tournament")


@admin.register(MergeLog)
class MergeLogAdmin(admin.ModelAdmin):
    autocomplete_fields = ("player", "source_ball1", "source_ball2", "result_ball")
    list_display = ("player", "result_ball", "created_at")
