from __future__ import annotations

from bd_models.models import Player
from fcdex_3_0.models import Tournament, TournamentGroup, TournamentMatch, TournamentRegistration


async def list_pending_matches(tournament: Tournament, player: Player) -> list[TournamentMatch]:
    matches: list[TournamentMatch] = []
    async for match in (
        tournament.matches.filter(completed=False).select_related("player1", "player2").order_by("round", "created_at")
    ):
        if match.player1_id == player.pk or match.player2_id == player.pk:
            matches.append(match)
    return matches


async def claim_match_victory(tournament: Tournament, match: TournamentMatch, winner: Player) -> tuple[bool, str]:
    if match.completed:
        return False, "This match is already completed."
    if winner.pk not in (match.player1_id, match.player2_id):
        return False, "You aren't a participant in this match."
    if match.player2_id is None:
        return False, "This match has no opponent yet."

    match.winner = winner
    match.completed = True
    if winner.pk == match.player1_id:
        match.score1, match.score2 = 1, 0
    else:
        match.score1, match.score2 = 0, 1

    reward = tournament.match_win_reward
    reward_text = ""
    if reward and not match.reward_claimed:
        await winner.add_money(reward)
        match.reward_claimed = True
        reward_text = f" · **+{reward:,}** coins"

    await match.asave(update_fields=("winner", "completed", "score1", "score2", "reward_claimed"))

    try:
        registration = await TournamentRegistration.objects.aget(tournament=tournament, player=winner)
        registration.score += 3
        if tournament.semifinal_cutoff and registration.score < tournament.semifinal_cutoff:
            registration.semifinal_eligible = False
        await registration.asave(update_fields=("score", "semifinal_eligible"))
    except TournamentRegistration.DoesNotExist:
        pass

    opponent = match.player2 if winner.pk == match.player1_id else match.player1
    try:
        group_part = f" · **{TournamentGroup(match.group).label}**" if match.group else ""
    except ValueError:
        group_part = ""
    opponent_mention = f"<@{opponent.discord_id}>" if opponent else "your opponent"
    return True, (
        f"🏆 Match **#{match.pk}** recorded{group_part}! "
        f"You beat {opponent_mention} · **+3** tournament pts{reward_text}"
    )
