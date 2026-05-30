from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay, button

from ballsdex.core.discord import LayoutView
from bd_models.models import Player
from fcdex_3_0.fcdex_ext.tournament_match import claim_match_victory, list_pending_matches
from fcdex_3_0.fcdex_ext.views import truncate_text
from fcdex_3_0.models import Tournament, TournamentGroup, TournamentMatch, TournamentRound, TournamentStatus

if TYPE_CHECKING:
    from discord import Interaction

ROUND_LABELS = {
    TournamentRound.GROUP: "Group stage",
    TournamentRound.SEMIFINAL: "Semifinals",
    TournamentRound.FINAL: "Finals",
}


def _group_label(value: str | None) -> str:
    if not value:
        return ""
    try:
        return TournamentGroup(value).label
    except ValueError:
        return value.title()


def format_match_line(match: TournamentMatch, *, index: int | None = None) -> str:
    prefix = f"**M{index}** · " if index else ""
    group = _group_label(match.group)
    group_tag = f"`{group}` · " if group else ""
    p1 = f"<@{match.player1.discord_id}>"
    p2 = f"<@{match.player2.discord_id}>" if match.player2 else "**BYE**"
    if match.completed and match.winner_id and match.winner:
        return f"{prefix}{group_tag}{p1} ~~vs~~ {p2} → 🏆 <@{match.winner.discord_id}>"
    return f"{prefix}{group_tag}{p1} **vs** {p2} · ⏳ Pending"


def _round_label(value: str) -> str:
    try:
        return ROUND_LABELS[TournamentRound(value)]
    except (ValueError, KeyError):
        return value.replace("_", " ").title()


async def build_seeding_sections(tournament: Tournament) -> list[str]:
    sections: list[str] = []
    for group in TournamentGroup:
        regs = [
            r
            async for r in tournament.registrations.filter(group=group.value)
            .select_related("player")
            .order_by("-score", "player_id")
        ]
        if not regs:
            sections.append(f"### 🛡️ {group.label} · Seeding\n*No players registered yet*")
            continue
        lines = [
            f"`Seed {seed:02d}` <@{reg.player.discord_id}> · **{group.label}**" for seed, reg in enumerate(regs, 1)
        ]
        if tournament.status == TournamentStatus.REGISTRATION:
            hint = "-# Pairings generate when the host **starts the group stage** via `/tournament manage`."
        else:
            hint = "-# Group stage not started yet — waiting on the host."
        sections.append(f"### 🛡️ {group.label} · Seeding\n" + "\n".join(lines) + f"\n{hint}")
    return sections


async def build_bracket_sections(tournament: Tournament) -> list[str]:
    if await tournament.matches.acount() == 0:
        return await build_seeding_sections(tournament)

    sections: list[str] = []
    for group in TournamentGroup:
        group_matches = [
            m
            async for m in tournament.matches.filter(round=TournamentRound.GROUP, group=group.value)
            .select_related("player1", "player2", "winner")
            .order_by("pk")
        ]
        if not group_matches:
            continue
        lines = [format_match_line(m, index=i) for i, m in enumerate(group_matches, start=1)]
        sections.append(f"### 📋 {group.label} · Group stage\n" + "\n".join(lines))

    for round_value, round_title in ((TournamentRound.SEMIFINAL, "Semifinals"), (TournamentRound.FINAL, "Grand final")):
        knockout = [
            m
            async for m in tournament.matches.filter(round=round_value)
            .select_related("player1", "player2", "winner")
            .order_by("group", "pk")
        ]
        if not knockout:
            continue
        blocks = [
            f"**{round_title}{' · `' + _group_label(m.group) + '`' if m.group else ''}**\n"
            f"{format_match_line(m, index=i)}"
            for i, m in enumerate(knockout, start=1)
        ]
        sections.append(f"### 🗂️ {round_title}\n\n" + "\n\n".join(blocks))

    return sections or await build_seeding_sections(tournament)


async def build_match_hub_body(tournament: Tournament, player: Player) -> tuple[str, list[TournamentMatch]]:
    pending = await list_pending_matches(tournament, player)
    if not pending:
        return (
            f"No pending matches in **{tournament.name}**.\n"
            "-# Register via `/tournament view`, then wait for the host to start the group stage.",
            [],
        )

    lines: list[str] = []
    for match in pending:
        opponent = match.player2 if match.player1_id == player.pk else match.player1
        if opponent is None:
            continue
        round_name = _round_label(match.round)
        group = _group_label(match.group)
        reward = tournament.match_win_reward
        lines.append(
            f"**Match #{match.pk}** · `{round_name}` · **{group}** group\n"
            f"You **vs** <@{opponent.discord_id}>\n"
            f"-# Reward: **{reward:,}** coins + **3** pts · claim after winning your battle"
        )
    return "\n\n".join(lines), pending


class MatchPickSelect(discord.ui.Select):
    def __init__(self, owner_id: int, matches: list[TournamentMatch]):
        self.owner_id = owner_id
        super().__init__(
            placeholder="Select a match…",
            options=[
                discord.SelectOption(label=f"#{m.pk} · {_group_label(m.group)} · vs opponent", value=str(m.pk))
                for m in matches[:25]
            ],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu is for the player who opened it.", ephemeral=True)
            return
        view: TournamentMatchMenuLayout = self.view  # type: ignore[assignment]
        view.selected_match_id = int(self.values[0])
        await interaction.response.send_message(f"Selected match **#{self.values[0]}**.", ephemeral=True)


class TournamentMatchClaimRow(ActionRow):
    def __init__(self, owner_id: int, tournament_id: int):
        super().__init__()
        self.owner_id = owner_id
        self.tournament_id = tournament_id

    @button(label="Claim victory", style=discord.ButtonStyle.success, emoji="🏆")
    async def claim_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This menu is for the player who opened it.", ephemeral=True)
            return
        view: TournamentMatchMenuLayout = self.view  # type: ignore[assignment]
        if not view.pending:
            await interaction.response.send_message("You have no pending matches.", ephemeral=True)
            return

        tournament = await Tournament.objects.aget(pk=self.tournament_id)
        match = await TournamentMatch.objects.select_related("player1", "player2").aget(pk=view.selected_match_id)
        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        ok, message = await claim_match_victory(tournament, match, player)
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        layout = await build_tournament_match_menu(self.owner_id, self.tournament_id, notice=message)
        await interaction.response.edit_message(view=layout)


class TournamentMatchMenuLayout(LayoutView):
    def __init__(self, owner_id: int, tournament_id: int, *, pending: list[TournamentMatch], header: str, body: str):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.tournament_id = tournament_id
        self.pending = pending
        self.selected_match_id = pending[0].pk if pending else 0

        container = Container()
        container.add_item(TextDisplay(truncate_text(f"{header}\n\n{body}")))
        if pending:
            container.add_item(Separator())
            row = ActionRow()
            row.add_item(MatchPickSelect(owner_id, pending))
            container.add_item(row)
            container.add_item(TournamentMatchClaimRow(owner_id, tournament_id))
        self.add_item(container)


async def build_tournament_match_menu(owner_id: int, tournament_id: int, *, notice: str = "") -> LayoutView:
    tournament = await Tournament.objects.aget(pk=tournament_id)
    player, _ = await Player.objects.aget_or_create(discord_id=owner_id)
    body, pending = await build_match_hub_body(tournament, player)

    header = "# ⚔️ Tournament matches"
    if notice:
        header += f"\n{notice}"
    header += f"\n-# **{tournament.name}** · **{tournament.match_win_reward:,}** coins per win"

    return TournamentMatchMenuLayout(owner_id, tournament_id, pending=pending, header=header, body=body)
