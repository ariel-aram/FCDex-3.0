from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from django.utils import timezone

from ballsdex.core.discord import LayoutView
from bd_models.models import Player
from fcdex_3_0.fcdex_ext.tournament_match import claim_match_victory
from fcdex_3_0.models import Tournament, TournamentMatch

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("fcdex_3_0.tournament.battle")


async def find_open_match_between(tournament_id: int, player_a_id: int, player_b_id: int) -> TournamentMatch | None:
    pair = {player_a_id, player_b_id}
    async for match in (
        TournamentMatch.objects.filter(tournament_id=tournament_id, completed=False)
        .select_related("player1", "player2")
        .order_by("pk")
    ):
        if match.player2_id is None:
            continue
        if {match.player1_id, match.player2_id} == pair:
            return match
    return None


async def record_battle_verification(match_id: int, winner: Player) -> tuple[bool, str]:
    match = await TournamentMatch.objects.select_related("player1", "player2").aget(pk=match_id)
    if match.completed:
        return False, "This tournament match is already completed."
    if winner.pk not in (match.player1_id, match.player2_id):
        return False, "Battle winner is not a participant in this tournament match."

    updated = await TournamentMatch.objects.filter(pk=match_id, completed=False).aupdate(
        verified_winner_id=winner.pk, verified_at=timezone.now()
    )
    if not updated:
        return False, "This tournament match is already completed."
    return True, "Battle result verified."


async def apply_verified_battle_result(match_id: int, winner: Player, *, guild_id: int | None) -> tuple[bool, str]:
    match = await TournamentMatch.objects.aget(pk=match_id)
    if match.completed:
        return False, "This tournament match is already completed."
    tournament = await Tournament.objects.aget(pk=match.tournament_id)
    ok, message = await record_battle_verification(match_id, winner)
    if not ok:
        return False, message
    match = await TournamentMatch.objects.aget(pk=match_id)
    claimed, claim_message = await claim_match_victory(tournament, match, winner, guild_id=guild_id)
    if claimed:
        return True, claim_message
    return False, claim_message


async def start_tournament_match_battle(
    interaction: discord.Interaction, bot: BallsDexBot, match: TournamentMatch, initiator: discord.Member
) -> tuple[bool, str | LayoutView]:
    from fcdex_3_0.fcdex_ext.battle_cog import ActiveBattle, _active_battles, fetch_battle
    from fcdex_3_0.fcdex_ext.views import BattleLayoutView

    if not isinstance(interaction.guild, discord.Guild):
        return False, "Battles can only be started in a server."
    if match.completed:
        return False, "This tournament match is already finished."
    if match.player2_id is None:
        return False, "This match has no opponent yet."

    player, _ = await Player.objects.aget_or_create(discord_id=initiator.id)
    if player.pk not in (match.player1_id, match.player2_id):
        return False, "You aren't a participant in this tournament match."

    opponent_player_id = match.player2_id if player.pk == match.player1_id else match.player1_id
    opponent_player = await Player.objects.aget(pk=opponent_player_id)
    opponent_member = interaction.guild.get_member(opponent_player.discord_id)
    if opponent_member is None:
        return False, "Your opponent must be in this server to start a battle."

    if opponent_member.bot:
        return False, "You can't battle bots."
    if fetch_battle(initiator) or fetch_battle(opponent_member):
        return False, "One of you is already in a match."

    battle = ActiveBattle(interaction, initiator, opponent_member, bot, tournament_match_id=match.pk)
    _active_battles.append(battle)
    tournament = await Tournament.objects.aget(pk=match.tournament_id)
    layout = BattleLayoutView(
        battle,
        banner=(
            f"🏟️ **{tournament.name}** · match **#{match.pk}**\n"
            f"{initiator.mention} vs {opponent_member.mention} — lock in when ready!"
        ),
    )
    return True, layout
