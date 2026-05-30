from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from fcdex_3_0.fcdex_ext.views import build_panel_layout

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class FcdexCog(commands.GroupCog, group_name="fcdex"):
    """FCDex 3.0 feature directory."""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot

    @app_commands.command(name="menu", description="FCDex 3.0 hub — battles, tournaments, merge forge, achievements")
    async def menu(self, interaction: discord.Interaction):
        layout = build_panel_layout(
            title="FCDex 3.0",
            subtitle="Official extra · Components v2 hubs",
            sections=[
                "### ⚔️ Battles\n`/battle challenge` — challenge a player\n`/battle card` — manage your battle lineup",
                "### 🏟️ Tournaments\n"
                "`/tournament view` — hub, join, standings, bracket\n"
                "`/tournament match` — battles, bounties, verified wins\n"
                "`/tournament bet` · `/tournament rules`\n"
                "`/tournament manage` — admin panel (Manage Server)",
                "### ✨ Merge forge\n"
                "`/merge menu` — step-by-step merge special crafting\n"
                "`/merge clubs` — quick two-card merge\n"
                "`/merge info` — how merge specials work",
                "### 🏅 Achievements\n`/achievement menu` — catalog, progress, claim rewards",
            ],
            footer="-# Configure achievements & tournaments in the admin panel under FCDex 3.0",
        )
        await interaction.response.send_message(view=layout)  # pyright: ignore[reportArgumentType]
