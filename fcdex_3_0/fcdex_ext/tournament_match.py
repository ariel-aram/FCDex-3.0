from __future__ import annotations

from bd_models.models import Player
from fcdex_3_0.fcdex_ext.tournament_bets import resolve_bets_for_match
from fcdex_3_0.fcdex_ext.tournament_loot import grant_match_loot, load_match_prizes
from fcdex_3_0.models import Tournament, TournamentGroup, TournamentMatch, TournamentRegistration


async def list_pending_matches(tournament: Tournament, player: Player) -> list[TournamentMatch]:
    matches: list[TournamentMatch] = []
    async for match in (
        tournament.matches.filter(completed=False).select_related("player1", "player2").order_by("round", "created_at")
    ):
        if match.player1_id == player.pk or match.player2_id == player.pk:
            matches.append(match)
    return matches


async def claim_match_victory(
    tournament: Tournament, match: TournamentMatch, winner: Player, *, guild_id: int | None = None
) -> tuple[bool, str]:
    if winner.pk not in (match.player1_id, match.player2_id):
        return False, "You aren't a participant in this match."
    if match.player2_id is None:
        return False, "This match has no opponent yet."

    fresh = await TournamentMatch.objects.aget(pk=match.pk)
    if fresh.completed:
        return False, "This match is already completed."
    if fresh.verified_winner_id is None:
        return False, (
            "No verified battle result yet — use **Start battle** in this hub, win the match, then claim your rewards."
        )
    if fresh.verified_winner_id != winner.pk:
        return False, "Only the verified battle winner can claim this match."

    score1, score2 = (1, 0) if winner.pk == match.player1_id else (0, 1)
    locked = await TournamentMatch.objects.filter(pk=match.pk, completed=False, verified_winner_id=winner.pk).aupdate(
        winner_id=winner.pk, completed=True, score1=score1, score2=score2
    )
    if not locked:
        return False, "This match is already completed."

    match = await TournamentMatch.objects.aget(pk=match.pk)

    reward_text = ""
    if not match.reward_claimed:
        prize_pool = await load_match_prizes(match)
        loot_text = await grant_match_loot(match, winner, guild_id=guild_id)
        reward_text = f" · {loot_text}"
        if not prize_pool and tournament.match_win_reward:
            await winner.add_money(tournament.match_win_reward)
            reward_text += f" · **+{tournament.match_win_reward:,}** coins"
        await TournamentMatch.objects.filter(pk=match.pk, reward_claimed=False).aupdate(reward_claimed=True)

    try:
        registration = await TournamentRegistration.objects.aget(tournament=tournament, player=winner)
        registration.score += 3
        if tournament.semifinal_cutoff and registration.score < tournament.semifinal_cutoff:
            registration.semifinal_eligible = False
        await registration.asave(update_fields=("score", "semifinal_eligible"))
    except TournamentRegistration.DoesNotExist:
        pass

    bet_lines = await resolve_bets_for_match(match, winner)
    bet_text = f"\n-# Bets settled: {', '.join(bet_lines)}" if bet_lines else ""

    opponent = match.player2 if winner.pk == match.player1_id else match.player1
    try:
        group_part = f" · **{TournamentGroup(match.group).label}**" if match.group else ""
    except ValueError:
        group_part = ""
    opponent_mention = f"<@{opponent.discord_id}>" if opponent else "your opponent"
    return True, (
        f"🏆 Match **#{match.pk}** recorded{group_part}! "
        f"You beat {opponent_mention} · **+3** tournament pts{reward_text}{bet_text}"
    )
