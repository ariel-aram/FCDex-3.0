from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import discord

from bd_models.models import Ball, BallInstance, Player, balls
from fcdex_3_0.fcdex_ext.bd_helpers import format_instance
from fcdex_3_0.fcdex_ext.merge_special import get_merge_special
from fcdex_3_0.fcdex_ext.services import increment_stat
from fcdex_3_0.models import MergeLog
from settings.models import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class MergeValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def validate_merge_pair(player: Player, first: BallInstance, second: BallInstance) -> None:
    if first.pk == second.pk:
        raise MergeValidationError("Pick two different clubballs.")
    if first.player_id != player.pk or second.player_id != player.pk:
        raise MergeValidationError(f"Both {settings.plural_collectible_name} must belong to you.")
    if first.deleted or second.deleted:
        raise MergeValidationError("One of these cards is no longer available.")
    if await first.is_locked() or await second.is_locked():
        raise MergeValidationError("One of these cards is locked for a trade.")


async def load_mergeable_instances(player: Player, *, exclude_id: int | None = None) -> list[BallInstance]:
    instances: list[BallInstance] = []
    queryset = BallInstance.objects.filter(player=player, deleted=False).select_related("ball").order_by("-pk")
    async for instance in queryset[:50]:
        if exclude_id is not None and instance.pk == exclude_id:
            continue
        if await instance.is_locked():
            continue
        instances.append(instance)
        if len(instances) >= 25:
            break
    return instances


async def resolve_result_ball(first: BallInstance, second: BallInstance) -> Ball:
    parent_balls: list[Ball] = []
    for pk in {first.ball_id, second.ball_id}:
        ball = balls.get(pk)
        if ball is None:
            ball = await Ball.objects.aget(pk=pk)
        parent_balls.append(ball)
    enabled_parents = [ball for ball in parent_balls if ball.enabled]
    if enabled_parents:
        return random.choice(enabled_parents)
    enabled = [ball for ball in balls.values() if ball.enabled]
    if not enabled:
        raise MergeValidationError("No clubballs are available to merge into right now.")
    return random.choices(enabled, weights=[ball.rarity for ball in enabled], k=1)[0]


async def execute_merge(
    player: Player, first: BallInstance, second: BallInstance, *, guild_id: int | None, bot: BallsDexBot
) -> tuple[BallInstance, str, discord.File]:
    await validate_merge_pair(player, first, second)
    merge_special = await get_merge_special()
    result_ball = await resolve_result_ball(first, second)

    attack_bonus = random.randint(-settings.max_attack_bonus, settings.max_attack_bonus)
    health_bonus = random.randint(-settings.max_health_bonus, settings.max_health_bonus)

    first.deleted = True
    second.deleted = True
    await first.asave(update_fields=("deleted",))
    await second.asave(update_fields=("deleted",))

    new_instance = await BallInstance.objects.acreate(
        ball=result_ball,
        player=player,
        special=merge_special,
        attack_bonus=attack_bonus,
        health_bonus=health_bonus,
        server_id=guild_id,
    )

    await MergeLog.objects.acreate(player=player, source_ball1=first, source_ball2=second, result_ball=new_instance)
    await increment_stat(player, "merges_completed")

    with ThreadPoolExecutor() as pool:
        buffer = await bot.loop.run_in_executor(pool, new_instance.draw_card)

    result_label = await format_instance(new_instance)
    special_tag = merge_special.emoji or "✨"
    summary = (
        f"{special_tag} **{merge_special.name}** merge complete!\n"
        f"You forged `{result_label}` (`{attack_bonus:+}%` / `{health_bonus:+}%`)."
    )
    return new_instance, summary, discord.File(buffer, "card.webp")
