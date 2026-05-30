from __future__ import annotations

import logging
import random
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.utils.buttons import ConfirmChoiceView
from ballsdex.core.utils.transformers import BallInstanceTransform
from bd_models.models import BallInstance, Player, balls
from fcdex_3_0.fcdex_ext.bd_helpers import format_instance
from fcdex_3_0.fcdex_ext.services import increment_stat
from fcdex_3_0.models import MergeLog
from settings.models import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("fcdex_3_0.merge")


class MergeCog(commands.GroupCog, group_name="merge"):
    """Merge clubballs to discover a random new club."""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot

    @app_commands.command(name="clubs", description="Merge two clubballs into a random new clubball")
    async def merge_clubs(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        first: BallInstanceTransform,
        second: BallInstanceTransform,
    ):
        if first.pk == second.pk:
            await interaction.response.send_message("You need two different clubballs to merge.", ephemeral=True)
            return

        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        if first.player_id != player.pk or second.player_id != player.pk:
            await interaction.response.send_message(
                f"Both {settings.plural_collectible_name} must belong to you.", ephemeral=True
            )
            return

        if first.deleted or second.deleted:
            await interaction.response.send_message("One of these cards is no longer available.", ephemeral=True)
            return

        if await first.is_locked() or await second.is_locked():
            await interaction.response.send_message("One of these cards is locked for a trade.", ephemeral=True)
            return

        enabled = [b for b in balls.values() if b.enabled]
        if not enabled:
            await interaction.response.send_message(
                "No clubballs are available to merge into right now.", ephemeral=True
            )
            return

        first_label = await format_instance(first)
        second_label = await format_instance(second)
        view = ConfirmChoiceView(interaction, accept_message="Merge confirmed!", cancel_message="Merge cancelled.")
        await interaction.response.send_message(
            f"Merge `{first_label}` + `{second_label}` "
            f"into a **random** {settings.collectible_name}?\n"
            f"-# Both cards will be consumed.",
            view=view,
            ephemeral=True,
        )
        await view.wait()
        if view.value is not True:
            return

        result_ball = random.choices(enabled, weights=[b.rarity for b in enabled], k=1)[0]
        attack_bonus = random.randint(-settings.max_attack_bonus, settings.max_attack_bonus)
        health_bonus = random.randint(-settings.max_health_bonus, settings.max_health_bonus)

        first.deleted = True
        second.deleted = True
        await first.asave(update_fields=("deleted",))
        await second.asave(update_fields=("deleted",))

        new_instance = await BallInstance.objects.acreate(
            ball=result_ball,
            player=player,
            attack_bonus=attack_bonus,
            health_bonus=health_bonus,
            server_id=interaction.guild_id,
        )

        await MergeLog.objects.acreate(player=player, source_ball1=first, source_ball2=second, result_ball=new_instance)
        await increment_stat(player, "merges_completed")

        with ThreadPoolExecutor() as pool:
            buffer = await interaction.client.loop.run_in_executor(pool, new_instance.draw_card)

        result_label = await format_instance(new_instance)
        await interaction.followup.send(
            f"✨ Merge complete! You received `{result_label}` "
            f"(`{attack_bonus:+}%`/`{health_bonus:+}%`).",
            file=discord.File(buffer, "card.webp"),
        )
