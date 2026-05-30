from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.utils.transformers import TTLModelTransformer
from fcdex_3_0.fcdex_ext.achievement_views import build_achievement_menu
from fcdex_3_0.models import Achievement

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

    @app_commands.command(name="menu", description="Browse achievements, track progress, and claim rewards")
    async def menu(self, interaction: discord.Interaction, user: discord.User | None = None):
        target = user or interaction.user
        layout = await build_achievement_menu(interaction.user.id, mode="catalog", target=target)
        await interaction.response.send_message(view=layout)  # pyright: ignore[reportArgumentType]
