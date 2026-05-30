from __future__ import annotations

import itertools
import logging
import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from django.utils import timezone

from ballsdex.core.utils.transformers import TTLModelTransformer
from bd_models.models import Player
from fcdex_3_0.fcdex_ext.services import increment_stat
from fcdex_3_0.fcdex_ext.tournament_match_views import build_tournament_match_menu
from fcdex_3_0.fcdex_ext.tournament_player_views import build_tournament_player_menu
from fcdex_3_0.fcdex_ext.tournament_schedule import past_end_reason, start_blocked_reason
from fcdex_3_0.fcdex_ext.tournament_views import TournamentManageView
from fcdex_3_0.models import (
    Tournament,
    TournamentGroup,
    TournamentMatch,
    TournamentRegistration,
    TournamentRound,
    TournamentStatus,
)

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("fcdex_3_0.tournament")


class TournamentTransformer(TTLModelTransformer[Tournament]):
    name = "tournament"
    column = "name"
    model = Tournament

    def get_queryset(self):
        return super().get_queryset().exclude(status=TournamentStatus.COMPLETED)

    async def get_from_pk(self, value: int) -> Tournament:
        return await self.get_queryset().select_related("host").aget(pk=value)


TournamentTransform = app_commands.Transform[Tournament, TournamentTransformer]


class TournamentCog(commands.GroupCog, group_name="tournament"):
    """Legacy & Main group tournaments with bracket progression."""

    def __init__(self, bot: BallsDexBot):
        self.bot = bot

    @app_commands.command(name="manage", description="Admin panel — create, edit, delete, and run tournaments")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def manage(self, interaction: discord.Interaction):
        view = TournamentManageView(interaction.user.id)
        await interaction.response.send_message(view=view, ephemeral=True)  # pyright: ignore[reportArgumentType]

    @app_commands.command(name="view", description="Tournament hub — overview, standings, bracket, and join")
    async def view(self, interaction: discord.Interaction, tournament: TournamentTransform):
        layout = await build_tournament_player_menu(interaction.user.id, tournament.pk, mode="overview")
        await interaction.response.send_message(view=layout)  # pyright: ignore[reportArgumentType]

    @app_commands.command(name="match", description="View pending matches and claim victory rewards")
    async def match(self, interaction: discord.Interaction, tournament: TournamentTransform):
        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        try:
            await TournamentRegistration.objects.aget(tournament=tournament, player=player)
        except TournamentRegistration.DoesNotExist:
            await interaction.response.send_message(
                "You must join this tournament first — use `/tournament view`.", ephemeral=True
            )
            return
        layout = await build_tournament_match_menu(interaction.user.id, tournament.pk)
        await interaction.response.send_message(view=layout)  # pyright: ignore[reportArgumentType]

    @app_commands.command(name="score", description="Report your match score (group stage)")
    async def score(
        self,
        interaction: discord.Interaction,
        tournament: TournamentTransform,
        points: app_commands.Range[int, -100, 100],
    ):
        if reason := past_end_reason(tournament):
            await interaction.response.send_message(reason, ephemeral=True)
            return

        if tournament.status not in (TournamentStatus.GROUP_STAGE, TournamentStatus.REGISTRATION):
            await interaction.response.send_message(
                "Scores can only be updated during registration or group stage.", ephemeral=True
            )
            return

        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        try:
            registration = await TournamentRegistration.objects.aget(tournament=tournament, player=player)
        except TournamentRegistration.DoesNotExist:
            await interaction.response.send_message("You're not registered in this tournament.", ephemeral=True)
            return

        registration.score += points
        if tournament.semifinal_cutoff and registration.score < tournament.semifinal_cutoff:
            registration.semifinal_eligible = False
        await registration.asave(update_fields=("score", "semifinal_eligible"))

        await interaction.response.send_message(
            f"Score updated! You're now at **{registration.score}** points in the "
            f"**{registration.get_group_display()}** group."
            + ("" if registration.semifinal_eligible else "\n-# ⚠️ Below semifinal cutoff.")
        )


async def run_tournament_start(tournament: Tournament) -> str | None:
    if tournament.status != TournamentStatus.REGISTRATION:
        return "This tournament has already started."
    if reason := start_blocked_reason(tournament):
        return reason
    count = await tournament.registrations.acount()
    if count < 2:
        return "Need at least 2 players to start."

    tournament.status = TournamentStatus.GROUP_STAGE
    tournament.started_at = timezone.now()
    await tournament.asave(update_fields=("status", "started_at"))

    for group in TournamentGroup:
        players = [
            reg.player async for reg in tournament.registrations.filter(group=group.value).select_related("player")
        ]
        for p1, p2 in itertools.combinations(players, 2):
            await TournamentMatch.objects.acreate(
                tournament=tournament, round=TournamentRound.GROUP, group=group.value, player1=p1, player2=p2
            )
    return None


async def run_tournament_advance(tournament: Tournament) -> tuple[bool, str]:
    if reason := past_end_reason(tournament):
        return False, reason

    if tournament.status == TournamentStatus.GROUP_STAGE:
        eliminated = 0
        for group in TournamentGroup:
            regs = [
                r
                async for r in tournament.registrations.filter(group=group.value)
                .select_related("player")
                .order_by("-score")
            ]
            if len(regs) <= 1:
                continue
            cutoff_index = max(1, len(regs) // 2)
            for reg in regs[cutoff_index:]:
                if not reg.semifinal_eligible or reg.score < tournament.semifinal_cutoff:
                    reg.eliminated = True
                    await reg.asave(update_fields=("eliminated",))
                    eliminated += 1

            finalists = [r for r in regs if not r.eliminated][:2]
            if len(finalists) == 2:
                await TournamentMatch.objects.acreate(
                    tournament=tournament,
                    round=TournamentRound.SEMIFINAL,
                    group=group.value,
                    player1=finalists[0].player,
                    player2=finalists[1].player,
                )

        tournament.status = TournamentStatus.SEMIFINALS
        await tournament.asave(update_fields=("status",))
        return True, f"Semifinals started! **{eliminated}** players eliminated for low scores."

    if tournament.status == TournamentStatus.SEMIFINALS:
        winners: list[Player] = []
        async for match in tournament.matches.filter(round=TournamentRound.SEMIFINAL, completed=False).select_related(
            "player1", "player2"
        ):
            if match.player2 is None:
                continue
            winner = random.choice([match.player1, match.player2])
            match.winner = winner
            match.completed = True
            await match.asave(update_fields=("winner", "completed"))
            winners.append(winner)

        if len(winners) >= 2:
            await TournamentMatch.objects.acreate(
                tournament=tournament, round=TournamentRound.FINAL, player1=winners[0], player2=winners[1]
            )
            tournament.status = TournamentStatus.FINALS
            await tournament.asave(update_fields=("status",))
            return True, "Finals match created! Bring your best teams."
        return False, "Not enough semifinal winners to create a final."

    if tournament.status == TournamentStatus.FINALS:
        final = (
            await tournament.matches.filter(round=TournamentRound.FINAL, completed=False)
            .select_related("player1", "player2")
            .afirst()
        )
        if not final or not final.player2:
            return False, "No pending final match found."

        winner = random.choice([final.player1, final.player2])
        final.winner = winner
        final.completed = True
        await final.asave(update_fields=("winner", "completed"))

        tournament.status = TournamentStatus.COMPLETED
        tournament.ended_at = timezone.now()
        await tournament.asave(update_fields=("status", "ended_at"))
        await increment_stat(winner, "tournament_wins")
        return True, f"🏆 **{tournament.name}** complete! Winner: <@{winner.discord_id}>"

    return False, "This tournament cannot be advanced further."
