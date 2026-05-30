from __future__ import annotations

from django.utils import timezone

from bd_models.models import Ball, BallInstance, Player
from fcdex_3_0.models import Achievement, AchievementType, PlayerAchievement, PlayerStats


async def get_or_create_stats(player: Player) -> PlayerStats:
    stats, _ = await PlayerStats.objects.aget_or_create(player=player)
    return stats


async def increment_stat(player: Player, stat: str, amount: int = 1) -> PlayerStats:
    stats = await get_or_create_stats(player)
    current = getattr(stats, stat, 0)
    setattr(stats, stat, current + amount)
    await stats.asave(update_fields=(stat,))
    await check_achievements(player)
    return stats


async def check_achievements(player: Player) -> None:
    stats = await get_or_create_stats(player)
    ball_count = await BallInstance.objects.filter(player=player, deleted=False).acount()

    stat_map = {
        AchievementType.BATTLES_WON: stats.battles_won,
        AchievementType.MERGES: stats.merges_completed,
        AchievementType.TOURNAMENT_WIN: stats.tournament_wins,
        AchievementType.TOURNAMENT_PARTICIPATE: stats.tournament_participations,
        AchievementType.BALLS_OWNED: ball_count,
    }

    async for achievement in Achievement.objects.filter(enabled=True).exclude(achievement_type=AchievementType.CUSTOM):
        try:
            achievement_type = AchievementType(achievement.achievement_type)
        except ValueError:
            continue
        progress = stat_map.get(achievement_type, 0)
        player_achievement, created = await PlayerAchievement.objects.aget_or_create(
            player=player, achievement=achievement, defaults={"progress": progress}
        )
        if not created and player_achievement.progress != progress:
            player_achievement.progress = progress
            await player_achievement.asave(update_fields=("progress",))

        complete = progress >= achievement.required_count
        if complete and not player_achievement.unlocked_at:
            player_achievement.unlocked_at = timezone.now()
            await player_achievement.asave(update_fields=("unlocked_at",))
        elif not complete and player_achievement.unlocked_at and not player_achievement.claimed_at:
            player_achievement.unlocked_at = None
            await player_achievement.asave(update_fields=("unlocked_at",))


def achievement_is_complete(player_achievement: PlayerAchievement, achievement: Achievement) -> bool:
    return player_achievement.progress >= achievement.required_count


async def claim_achievement(player: Player, achievement: Achievement) -> tuple[bool, str]:
    try:
        player_achievement = await PlayerAchievement.objects.select_related("achievement").aget(
            player=player, achievement=achievement
        )
    except PlayerAchievement.DoesNotExist:
        return False, "You haven't started this achievement yet."

    if not player_achievement.unlocked_at or not achievement_is_complete(player_achievement, achievement):
        return False, (
            f"This achievement is not complete yet "
            f"({player_achievement.progress}/{achievement.required_count})."
        )

    if player_achievement.claimed_at:
        return False, "You already claimed this achievement."

    if achievement.reward_money:
        await player.add_money(achievement.reward_money)

    if achievement.reward_ball_id:
        await BallInstance.objects.acreate(
            ball_id=achievement.reward_ball_id, player=player, attack_bonus=0, health_bonus=0
        )

    player_achievement.claimed_at = timezone.now()
    await player_achievement.asave(update_fields=("claimed_at",))

    rewards: list[str] = []
    if achievement.reward_money:
        rewards.append(f"{achievement.reward_money:,} coins")
    if achievement.reward_ball_id:
        ball = await Ball.objects.aget(pk=achievement.reward_ball_id)
        rewards.append(f"a {ball.country} card")

    reward_text = ", ".join(rewards) if rewards else "bragging rights"
    return True, f"Claimed **{achievement.name}**! Rewards: {reward_text}."
