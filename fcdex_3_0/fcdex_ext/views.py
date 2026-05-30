from __future__ import annotations

import io
from typing import TYPE_CHECKING

import discord
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay, button

from ballsdex.core.discord import LayoutView
from fcdex_3_0.fcdex_ext.battle_engine import BattleBall
from settings.models import settings

if TYPE_CHECKING:
    from fcdex_3_0.fcdex_ext.battle_cog import ActiveBattle

TEXT_DISPLAY_LIMIT = 4000


def truncate_text(text: str, limit: int = TEXT_DISPLAY_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_lineup(balls: list[BattleBall]) -> str:
    if not balls:
        return "No balls selected yet."
    lines = [f"- {ball.emoji} **{ball.name}** — HP {ball.health} / ATK {ball.attack}" for ball in balls]
    text = "\n".join(lines)
    return text[:950] + "\n…" if len(text) > 1024 else text


BATTLE_INSTRUCTIONS = (
    "### Battle instructions\n"
    "1. Use `/battle add` to pick clubballs for your lineup\n"
    "2. Use `/battle all` for a random lineup (up to 5)\n"
    "3. Use `/battle best` for your five strongest clubballs\n"
    "4. When your lineup is set, press **Lock Selection**\n"
    "5. When both players have locked, the match starts automatically\n\n"
    "### Damage basics\n"
    "- Base damage scales with attack power (±20% variance)\n"
    "- 30% chance to miss each strike\n"
    "- Full turn-by-turn **commentary** is shown when the match completes"
)


class BattleControls(ActionRow):
    def __init__(self, battle: ActiveBattle):
        super().__init__()
        self.battle = battle

    @button(label="Lock Selection", style=discord.ButtonStyle.success, emoji="🔒")
    async def ready_button(self, interaction: discord.Interaction, button: Button):
        await self.battle.mark_ready(interaction)

    @button(label="Cancel Battle", style=discord.ButtonStyle.danger, emoji="✖")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await self.battle.cancel(interaction)


class BattleLayoutView(LayoutView):
    def __init__(self, battle: ActiveBattle, *, banner: str | None = None, interactive: bool = True):
        super().__init__(timeout=None)
        self.battle = battle
        self.banner = banner
        self.interactive = interactive and battle.is_active
        self._build()

    def _build(self):
        self.clear_items()
        container = Container()
        battle = self.battle

        locked = "🔒" if battle.author_ready else "⏳"
        opponent_locked = "🔒" if battle.opponent_ready else "⏳"

        if self.interactive:
            header = (
                f"{self.banner}\n\n" if self.banner else ""
            ) + (
                f"# ⚔️ {settings.plural_collectible_name.title()} Battle\n"
                f"{battle.author.mention} vs {battle.opponent.mention}\n\n"
                f"Use `/battle add`, `/battle all`, or `/battle best`, "
                f"then press **Lock Selection** when your lineup is ready."
            )
        else:
            header = self.banner or "**This match has ended.**"

        container.add_item(TextDisplay(truncate_text(header)))
        container.add_item(Separator())
        container.add_item(
            TextDisplay(
                f"### {locked} {battle.author.display_name}'s battle lineup\n{format_lineup(battle.instance.p1_balls)}"
            )
        )
        container.add_item(Separator())
        container.add_item(
            TextDisplay(
                f"### {opponent_locked} {battle.opponent.display_name}'s battle lineup\n"
                f"{format_lineup(battle.instance.p2_balls)}"
            )
        )
        if self.interactive:
            container.add_item(Separator())
            container.add_item(TextDisplay(truncate_text(BATTLE_INSTRUCTIONS)))
            container.add_item(BattleControls(battle))
        self.add_item(container)


def build_battle_result_layout(battle: ActiveBattle, log_lines: list[str]) -> LayoutView:
    layout = LayoutView()
    container = Container()

    winner = battle.instance.winner
    container.add_item(
        TextDisplay(
            truncate_text(
                f"# 🏁 Match complete\n"
                f"{battle.author.mention} vs {battle.opponent.mention} — **{winner or 'Nobody'} wins!**\n"
                f"**Turns:** {battle.instance.turns}\n\n"
                f"### {battle.author.display_name}'s lineup\n{format_lineup(battle.instance.p1_balls)}\n\n"
                f"### {battle.opponent.display_name}'s lineup\n{format_lineup(battle.instance.p2_balls)}"
            )
        )
    )

    commentary = "\n".join(log_lines[-12:])
    if commentary:
        container.add_item(Separator())
        container.add_item(TextDisplay(truncate_text(f"### Commentary\n{commentary}")))

    layout.add_item(container)
    return layout


def build_achievement_layout(title: str, body: str) -> LayoutView:
    layout = LayoutView()
    container = Container()
    container.add_item(TextDisplay(truncate_text(f"# {title}\n{body}")))
    layout.add_item(container)
    return layout


def build_tournament_layout(title: str, sections: list[str]) -> LayoutView:
    layout = LayoutView()
    container = Container()
    container.add_item(TextDisplay(truncate_text(f"# {title}")))
    for section in sections:
        container.add_item(Separator())
        container.add_item(TextDisplay(truncate_text(section)))
    layout.add_item(container)
    return layout


def match_log_file(log_lines: list[str]) -> discord.File:
    return discord.File(io.BytesIO("\n".join(log_lines).encode()), filename="match-commentary.txt")


def battle_log_file(log_lines: list[str]) -> discord.File:
    return match_log_file(log_lines)
