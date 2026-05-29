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


def format_deck(balls: list[BattleBall]) -> str:
    if not balls:
        return "*Empty deck*"
    lines = [f"- {ball.emoji} **{ball.name}** — HP {ball.health} / ATK {ball.attack}" for ball in balls]
    text = "\n".join(lines)
    return text[:950] + "\n…" if len(text) > 1024 else text


class BattleControls(ActionRow):
    def __init__(self, battle: ActiveBattle):
        super().__init__()
        self.battle = battle

    @button(label="Ready", style=discord.ButtonStyle.success, emoji="✔")
    async def ready_button(self, interaction: discord.Interaction, button: Button):
        await self.battle.mark_ready(interaction)

    @button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await self.battle.cancel(interaction)


class BattleLayoutView(LayoutView):
    def __init__(self, battle: ActiveBattle, *, banner: str | None = None):
        super().__init__(timeout=None)
        self.battle = battle
        self.banner = banner
        self._build()

    def _build(self):
        self.clear_items()
        container = Container()
        battle = self.battle
        controls = BattleControls(battle)

        author_ready = "✅" if battle.author_ready else "⏳"
        opponent_ready = "✅" if battle.opponent_ready else "⏳"

        header = (
            f"{self.banner}\n\n" if self.banner else ""
        ) + (
            f"# ⚔️ {settings.plural_collectible_name.title()} Battle\n"
            f"{battle.author.mention} vs {battle.opponent.mention}\n\n"
            f"Use `/battle all` or `/battle best` to fill your deck, "
            f"then press **Ready** when done."
        )
        container.add_item(TextDisplay(header))
        container.add_item(Separator())
        container.add_item(
            TextDisplay(f"### {author_ready} {battle.author.display_name}\n{format_deck(battle.instance.p1_balls)}")
        )
        container.add_item(Separator())
        container.add_item(
            TextDisplay(f"### {opponent_ready} {battle.opponent.display_name}\n{format_deck(battle.instance.p2_balls)}")
        )
        container.add_item(controls)
        self.add_item(container)


def build_battle_result_layout(battle: ActiveBattle, log_lines: list[str]) -> LayoutView:
    layout = LayoutView()
    container = Container()

    winner = battle.instance.winner
    container.add_item(
        TextDisplay(
            f"# 🏆 Battle Complete\n"
            f"{battle.author.mention} vs {battle.opponent.mention} — **{winner} wins!**\n"
            f"**Turns:** {battle.instance.turns}\n\n"
            f"### {battle.author.display_name}\n{format_deck(battle.instance.p1_balls)}\n\n"
            f"### {battle.opponent.display_name}\n{format_deck(battle.instance.p2_balls)}"
        )
    )

    preview = "\n".join(log_lines[-8:])
    if preview:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"### Recent log\n{preview}"))

    layout.add_item(container)
    return layout


def build_achievement_layout(title: str, body: str) -> LayoutView:
    layout = LayoutView()
    container = Container()
    container.add_item(TextDisplay(f"# {title}\n{body}"))
    layout.add_item(container)
    return layout


def build_tournament_layout(title: str, sections: list[str]) -> LayoutView:
    layout = LayoutView()
    container = Container()
    container.add_item(TextDisplay(f"# {title}"))
    for section in sections:
        container.add_item(Separator())
        container.add_item(TextDisplay(section))
    layout.add_item(container)
    return layout


def battle_log_file(log_lines: list[str]) -> discord.File:
    return discord.File(io.BytesIO("\n".join(log_lines).encode()), filename="battle-log.txt")
