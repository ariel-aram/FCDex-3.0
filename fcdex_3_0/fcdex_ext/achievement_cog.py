from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.utils.transformers import TTLModelTransformer
from bd_models.models import Player
from fcdex_3_0.fcdex_ext.services import (
    achievement_is_complete,
    check_achievements,
    claim_achievement,
    get_or_create_stats,
)
from fcdex_3_0.fcdex_ext.views import build_achievement_layout
from fcdex_3_0.models import Achievement, PlayerAchievement

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("fcdex_3_0.achievement")


class AchievementTransformer(TTLModelTransformer[Achievement]):
    name = "achievement"
    column = "name"
    model = Achievement

    def get_queryset(self):
        return super().get_queryset().filter(enabled=True, hidden=False)


AchievementTransform = app_commands.Transform[Achievement, AchievementTransformer]


class AchievementCog(commands.GroupCog, group_name="achievement"):
    """Earn and claim FCDex achievements."""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot

    @app_commands.command(name="list", description="Browse available achievements")
    async def list_achievements(self, interaction: discord.Interaction):
        lines: list[str] = []
        async for achievement in (
            Achievement.objects.filter(enabled=True, hidden=False).select_related("reward_ball").order_by("name")
        ):
            reward = achievement.reward_ball
            lines.append(
                f"{achievement.emoji} **{achievement.name}** — {achievement.description}\n"
                f"-# Requires {achievement.required_count} · "
                f"Reward: {achievement.reward_money:,} coins" + (f" + {reward.country}" if reward else "")
            )

        if not lines:
            await interaction.response.send_message(
                "No achievements configured yet. Ask an admin to add some!", ephemeral=True
            )
            return

        body = "\n\n".join(lines[:25])
        layout = build_achievement_layout("🏅 Achievements", body)
        await interaction.response.send_message(view=layout, ephemeral=True)

    @app_commands.command(name="progress", description="View your achievement progress")
    async def progress(self, interaction: discord.Interaction, user: discord.User | None = None):
        target = user or interaction.user
        player, _ = await Player.objects.aget_or_create(discord_id=target.id)
        await get_or_create_stats(player)
        await check_achievements(player)

        lines: list[str] = []
        async for player_achievement in PlayerAchievement.objects.filter(player=player).select_related("achievement"):
            ach = player_achievement.achievement
            if ach.hidden and target.id != interaction.user.id:
                continue
            status = (
                "✅ Claimed"
                if player_achievement.claimed_at
                else (
                    "🎉 Ready to claim"
                    if achievement_is_complete(player_achievement, ach)
                    else "⏳ In progress"
                )
            )
            lines.append(
                f"{ach.emoji} **{ach.name}** — {player_achievement.progress}/{ach.required_count}\n-# {status}"
            )

        stats = await get_or_create_stats(player)
        header = (
            f"Stats for {target.display_name}\n"
            f"-# Battles won: {stats.battles_won} · Merges: {stats.merges_completed} · "
            f"Tournament wins: {stats.tournament_wins} · Tournaments joined: {stats.tournament_participations}"
        )
        body = header + ("\n\n" + "\n\n".join(lines) if lines else "\n\nNo achievement progress yet.")
        layout = build_achievement_layout("📊 Achievement Progress", body)
        await interaction.response.send_message(view=layout, ephemeral=True)

    @app_commands.command(name="claim", description="Claim a completed achievement reward")
    async def claim(self, interaction: discord.Interaction, achievement: AchievementTransform):  # pyright: ignore[reportInvalidTypeForm]
        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        await check_achievements(player)
        _success, message = await claim_achievement(player, achievement)
        await interaction.response.send_message(message, ephemeral=True)
