from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.utils.transformers import BallInstanceTransform
from bd_models.models import Player
from fcdex_3_0.fcdex_ext.merge_logic import MergeValidationError, validate_merge_pair
from fcdex_3_0.fcdex_ext.merge_views import build_merge_menu
from fcdex_3_0.fcdex_ext.views import build_panel_layout

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("fcdex_3_0.merge")


class MergeCog(commands.GroupCog, group_name="merge"):
    """Forge clubballs into FCDex merge specials."""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot

    @app_commands.command(name="menu", description="Open the merge forge — pick two cards and craft a merge special")
    async def menu(self, interaction: discord.Interaction):
        layout = await build_merge_menu(self.bot, interaction.user.id, step="intro")
        await interaction.response.send_message(view=layout)  # pyright: ignore[reportArgumentType]

    @app_commands.command(
        name="clubs", description="Quick merge — sacrifice two clubballs for a FCDex merge special card"
    )
    async def merge_clubs(
        self, interaction: discord.Interaction, first: BallInstanceTransform, second: BallInstanceTransform
    ):
        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        try:
            await validate_merge_pair(player, first, second)
        except MergeValidationError as exc:
            await interaction.response.send_message(exc.message, ephemeral=True)
            return

        layout = await build_merge_menu(
            self.bot, interaction.user.id, step="confirm", first_id=first.pk, second_id=second.pk
        )
        await interaction.response.send_message(view=layout)  # pyright: ignore[reportArgumentType]

    @app_commands.command(name="info", description="Learn how FCDex merging and merge specials work")
    async def info(self, interaction: discord.Interaction):
        from fcdex_3_0.fcdex_ext.merge_views import build_merge_intro_text

        layout = build_panel_layout(
            title="✨ FCDex merge forge",
            subtitle="Components v2 · merge special cards",
            sections=[await build_merge_intro_text()],
            footer="-# `/merge menu` to forge · `/merge clubs` for a fast two-card merge",
        )
        await interaction.response.send_message(view=layout)  # pyright: ignore[reportArgumentType]
