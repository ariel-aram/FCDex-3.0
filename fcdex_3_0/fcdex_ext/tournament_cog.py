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
from fcdex_3_0.fcdex_ext.tournament_schedule import (
    past_end_reason,
    registration_closed_reason,
    registration_is_open,
    schedule_summary_lines,
    start_blocked_reason,
)
from fcdex_3_0.fcdex_ext.tournament_views import TournamentManageView
from fcdex_3_0.fcdex_ext.views import build_tournament_layout
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

    @app_commands.command(name="manage", description="Admin panel: create, edit, or delete tournaments (ephemeral)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def manage(self, interaction: discord.Interaction):
        view = TournamentManageView(interaction.user.id)
        await interaction.response.send_message(view=view, ephemeral=True)  # pyright: ignore[reportArgumentType]

    @app_commands.command(name="join", description="Join an open tournament")
    @app_commands.choices(
        group=[app_commands.Choice(name="Legacy", value="legacy"), app_commands.Choice(name="Main", value="main")]
    )
    async def join(
        self, interaction: discord.Interaction, tournament: TournamentTransform, group: app_commands.Choice[str]
    ):
        if reason := registration_closed_reason(tournament):
            await interaction.response.send_message(reason, ephemeral=True)
            return

        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        registration, created = await TournamentRegistration.objects.aget_or_create(
            tournament=tournament, player=player, defaults={"group": group.value}
        )
        if not created:
            await interaction.response.send_message(
                f"You're already registered in the **{registration.get_group_display()}** group.", ephemeral=True
            )
            return

        await increment_stat(player, "tournament_participations")
        await interaction.response.send_message(
            f"Joined **{tournament.name}** as **{group.name}** group! Discuss strategy with your team.", ephemeral=True
        )

    @app_commands.command(name="info", description="Show tournament details")
    async def info(self, interaction: discord.Interaction, tournament: TournamentTransform):
        host_discord_id = await Player.objects.values_list("discord_id", flat=True).aget(pk=tournament.host_id)
        legacy_count = await tournament.registrations.filter(group=TournamentGroup.LEGACY).acount()
        main_count = await tournament.registrations.filter(group=TournamentGroup.MAIN).acount()

        schedule_lines = schedule_summary_lines(tournament)
        registration_note = (
            "Registration open"
            if registration_is_open(tournament)
            else (registration_closed_reason(tournament) or "Registration closed")
        )
        sections = [
            f"**Status:** {tournament.get_status_display()}\n"
            f"**Host:** <@{host_discord_id}>\n"
            f"**Registration:** {registration_note}\n"
            f"**Legacy group:** {legacy_count} players\n"
            f"**Main group:** {main_count} players\n"
            f"**Semifinal cutoff:** {tournament.semifinal_cutoff} pts"
            + ("\n" + "\n".join(schedule_lines) if schedule_lines else ""),
            tournament.description or "No description.",
        ]
        layout = build_tournament_layout(f"🏟️ {tournament.name}", sections)
        await interaction.response.send_message(view=layout, ephemeral=True)

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
            + ("" if registration.semifinal_eligible else "\n-# ⚠️ Below semifinal cutoff."),
            ephemeral=True,
        )

    @app_commands.command(name="standings", description="View group standings")
    async def standings(self, interaction: discord.Interaction, tournament: TournamentTransform):
        sections: list[str] = []
        for group in TournamentGroup:
            lines: list[str] = []
            queryset = (
                tournament.registrations.filter(group=group.value)
                .select_related("player")
                .order_by("-score", "player_id")
            )
            rank = 1
            async for reg in queryset:
                flag = "❌" if reg.eliminated else ("⚠️" if not reg.semifinal_eligible else "✅")
                lines.append(f"{rank}. <@{reg.player.discord_id}> — **{reg.score}** pts {flag}")
                rank += 1
            sections.append(f"### {group.label} Group\n" + ("\n".join(lines) if lines else "*No players yet*"))

        layout = build_tournament_layout(f"📊 {tournament.name} Standings", sections)
        await interaction.response.send_message(view=layout, ephemeral=True)

    @app_commands.command(name="start", description="Start the group stage (host/admin)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start(self, interaction: discord.Interaction, tournament: TournamentTransform):
        if tournament.status != TournamentStatus.REGISTRATION:
            await interaction.response.send_message("This tournament has already started.", ephemeral=True)
            return

        if reason := start_blocked_reason(tournament):
            await interaction.response.send_message(reason, ephemeral=True)
            return

        count = await tournament.registrations.acount()
        if count < 2:
            await interaction.response.send_message("Need at least 2 players to start.", ephemeral=True)
            return

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

        await interaction.response.send_message(
            f"**{tournament.name}** group stage started with **{count}** players! "
            f"Use `/battle challenge` for matches and `/tournament score` to track points."
        )

    @app_commands.command(name="advance", description="Advance to semifinals/finals (host/admin)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def advance(self, interaction: discord.Interaction, tournament: TournamentTransform):
        if reason := past_end_reason(tournament):
            await interaction.response.send_message(reason, ephemeral=True)
            return

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
            await interaction.response.send_message(
                f"Semifinals started! **{eliminated}** players eliminated for low scores."
            )
            return

        if tournament.status == TournamentStatus.SEMIFINALS:
            winners: list[Player] = []
            async for match in tournament.matches.filter(
                round=TournamentRound.SEMIFINAL, completed=False
            ).select_related("player1", "player2"):
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
                await interaction.response.send_message("Finals match created! Bring your best teams.")
            else:
                await interaction.response.send_message(
                    "Not enough semifinal winners to create a final.", ephemeral=True
                )
            return

        if tournament.status == TournamentStatus.FINALS:
            final = (
                await tournament.matches.filter(round=TournamentRound.FINAL, completed=False)
                .select_related("player1", "player2")
                .afirst()
            )
            if not final or not final.player2:
                await interaction.response.send_message("No pending final match found.", ephemeral=True)
                return

            winner = random.choice([final.player1, final.player2])
            final.winner = winner
            final.completed = True
            await final.asave(update_fields=("winner", "completed"))

            tournament.status = TournamentStatus.COMPLETED
            tournament.ended_at = timezone.now()
            await tournament.asave(update_fields=("status", "ended_at"))
            await increment_stat(winner, "tournament_wins")

            await interaction.response.send_message(
                f"🏆 **{tournament.name}** complete! Winner: <@{winner.discord_id}>\n"
                f"-# Group winners may share or keep rewards — check server rules."
            )
            return

        await interaction.response.send_message("This tournament cannot be advanced further.", ephemeral=True)

    @app_commands.command(name="bracket", description="View tournament bracket")
    async def bracket(self, interaction: discord.Interaction, tournament: TournamentTransform):
        sections: list[str] = []
        for round_label, round_value in TournamentRound.choices:
            lines: list[str] = []
            async for match in tournament.matches.filter(round=round_value).select_related(
                "player1", "player2", "winner"
            ):
                p2 = f"<@{match.player2.discord_id}>" if match.player2 else "BYE"
                status = (
                    f"Winner: <@{match.winner.discord_id}>"
                    if match.winner
                    else ("✅ Done" if match.completed else "⏳ Pending")
                )
                lines.append(f"<@{match.player1.discord_id}> vs {p2} — {status} ({match.score1}-{match.score2})")
            sections.append(f"### {round_label}\n" + ("\n".join(lines) if lines else "*No matches*"))

        layout = build_tournament_layout(f"🗂️ {tournament.name} Bracket", sections)
        await interaction.response.send_message(view=layout, ephemeral=True)
