from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.utils.transformers import BallInstanceTransform
from bd_models.models import BallInstance, Player
from fcdex_3_0.fcdex_ext.battle_engine import BattleBall, BattleInstance, gen_battle
from fcdex_3_0.fcdex_ext.bd_helpers import format_instance, get_ball, instance_attack, instance_health
from fcdex_3_0.fcdex_ext.services import increment_stat
from fcdex_3_0.fcdex_ext.views import BattleLayoutView, battle_log_file, build_battle_result_layout
from settings.models import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("fcdex_3_0.battle")

_active_battles: list[ActiveBattle] = []


@dataclass
class ActiveBattle:
    interaction: discord.Interaction
    author: discord.Member
    opponent: discord.Member
    instance: BattleInstance = field(default_factory=BattleInstance)
    author_ready: bool = False
    opponent_ready: bool = False
    cancelled: bool = False
    finished: bool = False

    def involves(self, user: discord.User | discord.Member) -> bool:
        return user.id in (self.author.id, self.opponent.id)

    @property
    def is_active(self) -> bool:
        return not self.cancelled and not self.finished

    def deck_for(self, user: discord.User | discord.Member) -> list[BattleBall]:
        return self.instance.p1_balls if user.id == self.author.id else self.instance.p2_balls

    def terminate(self) -> None:
        self.cancelled = True
        while self in _active_battles:
            _active_battles.remove(self)

    def close(self) -> None:
        self.finished = True
        while self in _active_battles:
            _active_battles.remove(self)

    async def refresh_message(self):
        if not self.is_active:
            return
        layout = BattleLayoutView(self)
        await self.interaction.edit_original_response(view=layout, attachments=[])

    async def _reject_inactive(self, interaction: discord.Interaction) -> bool:
        if self.is_active and self in _active_battles:
            return False
        await interaction.response.send_message("This match is no longer active.", ephemeral=True)
        return True

    async def mark_ready(self, interaction: discord.Interaction):
        if await self._reject_inactive(interaction):
            return
        if not self.involves(interaction.user):
            await interaction.response.send_message("You aren't in this battle.", ephemeral=True)
            return

        if interaction.user.id == self.author.id:
            self.author_ready = True
        else:
            self.opponent_ready = True

        if self.author_ready and self.opponent_ready:
            if not self.instance.p1_balls or not self.instance.p2_balls:
                self.author_ready = False
                self.opponent_ready = False
                await interaction.response.send_message(
                    f"Both players need at least one {settings.collectible_name} in their lineup!", ephemeral=True
                )
                if interaction.message and self.is_active:
                    await interaction.message.edit(view=BattleLayoutView(self))
                return
            await self._run_battle(interaction)
            return

        await interaction.response.send_message("You're locked in! Waiting for the other player.", ephemeral=True)
        if interaction.message and self.is_active:
            await interaction.message.edit(view=BattleLayoutView(self))

    def resolve_winner(self) -> discord.Member | None:
        winner_name = self.instance.winner
        if not winner_name:
            return None
        if winner_name == self.author.display_name:
            return self.author
        if winner_name == self.opponent.display_name:
            return self.opponent
        if any(not ball.dead for ball in self.instance.p1_balls) and not any(
            not ball.dead for ball in self.instance.p2_balls
        ):
            return self.author
        if any(not ball.dead for ball in self.instance.p2_balls) and not any(
            not ball.dead for ball in self.instance.p1_balls
        ):
            return self.opponent
        return None

    async def _run_battle(self, interaction: discord.Interaction):
        self.close()
        await interaction.response.defer()
        log_lines = list(gen_battle(self.instance))
        result_layout = build_battle_result_layout(self, log_lines)

        winner_member = self.resolve_winner()
        if winner_member is None:
            for member in (self.author, self.opponent):
                player, _ = await Player.objects.aget_or_create(discord_id=member.id)
                await increment_stat(player, "battles_played")
        else:
            loser_member = self.opponent if winner_member == self.author else self.author
            winner_player, _ = await Player.objects.aget_or_create(discord_id=winner_member.id)
            loser_player, _ = await Player.objects.aget_or_create(discord_id=loser_member.id)
            await increment_stat(winner_player, "battles_won")
            await increment_stat(winner_player, "battles_played")
            await increment_stat(loser_player, "battles_played")

        if interaction.message:
            await interaction.message.edit(view=result_layout, attachments=[battle_log_file(log_lines)])

    async def cancel(self, interaction: discord.Interaction):
        if await self._reject_inactive(interaction):
            return
        if not self.involves(interaction.user):
            await interaction.response.send_message("You aren't in this battle.", ephemeral=True)
            return

        self.terminate()
        await interaction.response.edit_message(
            view=BattleLayoutView(
                self,
                banner=f"**Match cancelled** — ended by {interaction.user.mention}.",
                interactive=False,
            ),
            attachments=[],
        )


def fetch_battle(user: discord.User | discord.Member) -> ActiveBattle | None:
    for battle in _active_battles:
        if battle.involves(user) and battle.is_active:
            return battle
    return None


async def ball_instance_to_battle_ball(instance: BallInstance, owner: str, bot: BallsDexBot) -> BattleBall:
    ball = await get_ball(instance)
    emoji = ""
    if emoji_obj := bot.get_emoji(ball.emoji_id):
        emoji = str(emoji_obj)
    return BattleBall(
        instance_id=instance.pk,
        name=ball.country,
        owner=owner,
        health=instance_health(instance, ball),
        attack=instance_attack(instance, ball),
        emoji=emoji,
    )


class BattleCog(commands.GroupCog, group_name="battle"):
    """Challenge friends to clubball battles."""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot

    @app_commands.command(name="challenge", description="Challenge a friend to a battle")
    async def challenge(self, interaction: discord.Interaction, opponent: discord.Member):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Battles can only be started in a server.", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("You can't battle bots.", ephemeral=True)
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You can't battle yourself.", ephemeral=True)
            return
        if fetch_battle(interaction.user) or fetch_battle(opponent):
            await interaction.response.send_message("One of you is already in a battle.", ephemeral=True)
            return

        author = interaction.user
        battle = ActiveBattle(interaction, author, opponent)
        _active_battles.append(battle)

        await interaction.response.send_message(
            view=BattleLayoutView(
                battle,
                banner=f"{author.mention} has challenged {opponent.mention} to a match!",
            ),  # pyright: ignore[reportArgumentType]
        )

    async def _fill_deck(self, interaction: discord.Interaction, *, mode: str):
        battle = fetch_battle(interaction.user)
        if battle is None or not battle.is_active:
            await interaction.response.send_message("You aren't in an active match.", ephemeral=True)
            return

        if interaction.guild_id != battle.interaction.guild_id:
            await interaction.response.send_message("You must be in the same server as your battle.", ephemeral=True)
            return

        ready = battle.author_ready if interaction.user.id == battle.author.id else battle.opponent_ready
        if ready:
            await interaction.response.send_message("You can't change your lineup after locking in.", ephemeral=True)
            return

        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        queryset = BallInstance.objects.filter(player=player, deleted=False)

        instances = [x async for x in queryset]
        if not instances:
            await interaction.response.send_message(
                f"You don't have any {settings.plural_collectible_name}.", ephemeral=True
            )
            return

        deck = battle.deck_for(interaction.user)
        deck.clear()

        if mode == "all":
            count = min(5, len(instances))
            chosen = random.sample(instances, count)
        elif mode == "best":
            scored: list[tuple[int, BallInstance]] = []
            for instance in instances:
                ball = await get_ball(instance)
                power = instance_attack(instance, ball) + instance_health(instance, ball)
                scored.append((power, instance))
            chosen = [instance for _, instance in sorted(scored, key=lambda item: item[0], reverse=True)[:5]]
        else:
            await interaction.response.send_message("Unknown deck mode.", ephemeral=True)
            return

        seen: set[int] = set()
        for instance in chosen:
            if instance.pk in seen:
                continue
            seen.add(instance.pk)
            deck.append(await ball_instance_to_battle_ball(instance, interaction.user.display_name, self.bot))

        await interaction.response.send_message(
            f"Lineup updated with **{len(deck)}** {settings.plural_collectible_name} ({mode})!", ephemeral=True
        )

        if not battle.is_active:
            return
        try:
            await battle.interaction.edit_original_response(view=BattleLayoutView(battle))
        except discord.HTTPException:
            log.exception("Failed to refresh battle layout")

    @app_commands.command(name="all", description="Fill your deck with random clubballs")
    async def all_balls(self, interaction: discord.Interaction):
        await self._fill_deck(interaction, mode="all")

    @app_commands.command(name="best", description="Fill your deck with your strongest clubballs")
    async def best_balls(self, interaction: discord.Interaction):
        await self._fill_deck(interaction, mode="best")

    @app_commands.command(name="add", description="Add a specific clubball to your battle deck")
    async def add_ball(self, interaction: discord.Interaction, clubball: BallInstanceTransform):
        battle = fetch_battle(interaction.user)
        if battle is None or not battle.is_active:
            await interaction.response.send_message("You aren't in an active match.", ephemeral=True)
            return

        ready = battle.author_ready if interaction.user.id == battle.author.id else battle.opponent_ready
        if ready:
            await interaction.response.send_message("You can't change your lineup after locking in.", ephemeral=True)
            return

        deck = battle.deck_for(interaction.user)
        if len(deck) >= 5:
            await interaction.response.send_message("Your lineup is full (max 5).", ephemeral=True)
            return

        ball = await ball_instance_to_battle_ball(clubball, interaction.user.display_name, self.bot)
        if any(x.instance_id == ball.instance_id for x in deck):
            await interaction.response.send_message("That card is already in your lineup.", ephemeral=True)
            return

        deck.append(ball)
        label = await format_instance(clubball)
        await interaction.response.send_message(f"Added `{label}`.", ephemeral=True)
        if battle.is_active:
            await battle.interaction.edit_original_response(view=BattleLayoutView(battle))

    @app_commands.command(name="remove", description="Remove a clubball from your battle deck")
    async def remove_ball(self, interaction: discord.Interaction, clubball: BallInstanceTransform):
        battle = fetch_battle(interaction.user)
        if battle is None or not battle.is_active:
            await interaction.response.send_message("You aren't in an active match.", ephemeral=True)
            return

        ready = battle.author_ready if interaction.user.id == battle.author.id else battle.opponent_ready
        if ready:
            await interaction.response.send_message("You can't change your lineup after locking in.", ephemeral=True)
            return

        deck = battle.deck_for(interaction.user)
        before = len(deck)
        deck[:] = [x for x in deck if x.instance_id != clubball.pk]
        if len(deck) == before:
            await interaction.response.send_message("That card isn't in your lineup.", ephemeral=True)
            return

        await interaction.response.send_message(f"Removed `{await format_instance(clubball)}`.", ephemeral=True)
        if battle.is_active:
            await battle.interaction.edit_original_response(view=BattleLayoutView(battle))
