from __future__ import annotations

from bd_models.models import Ball, BallInstance, balls


async def get_ball(instance: BallInstance) -> Ball:
    if cached := balls.get(instance.ball_id):
        return cached
    return await Ball.objects.aget(pk=instance.ball_id)


def instance_attack(instance: BallInstance, ball: Ball) -> int:
    bonus = int(ball.attack * instance.attack_bonus * 0.01)
    return ball.attack + bonus


def instance_health(instance: BallInstance, ball: Ball) -> int:
    bonus = int(ball.health * instance.health_bonus * 0.01)
    return ball.health + bonus


async def format_instance(instance: BallInstance) -> str:
    ball = await get_ball(instance)
    return f"#{instance.pk:0X} {ball.country}"
