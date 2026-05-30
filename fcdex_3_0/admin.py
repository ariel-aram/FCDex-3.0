from django.contrib import admin

from .models import (
    Achievement,
    MergeLog,
    PlayerAchievement,
    PlayerStats,
    Tournament,
    TournamentMatch,
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
        "scheduled_start_at",
        "scheduled_end_at",
        "semifinal_cutoff",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {"fields": ("name", "description", "host", "status", "semifinal_cutoff")}),
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
    autocomplete_fields = ("tournament", "player1", "player2", "winner")
    list_display = ("tournament", "round", "group", "player1", "player2", "winner", "completed")
    list_filter = ("round", "group", "completed", "tournament")


@admin.register(MergeLog)
class MergeLogAdmin(admin.ModelAdmin):
    autocomplete_fields = ("player", "source_ball1", "source_ball2", "result_ball")
    list_display = ("player", "result_ball", "created_at")
