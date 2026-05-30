from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import discord
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay, button

from ballsdex.core.discord import LayoutView
from bd_models.models import BallInstance, Player
from fcdex_3_0.fcdex_ext.bd_helpers import format_instance
from fcdex_3_0.fcdex_ext.merge_logic import (
    MergeValidationError,
    execute_merge,
    load_mergeable_instances,
    validate_merge_pair,
)
from fcdex_3_0.fcdex_ext.merge_special import MERGE_SPECIAL_NAME, get_merge_special
from fcdex_3_0.fcdex_ext.views import truncate_text
from settings.models import settings

if TYPE_CHECKING:
    from discord import Interaction

    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("fcdex_3_0.merge.views")


async def build_merge_intro_text() -> str:
    special = await get_merge_special()
    emoji = special.emoji or "✨"
    return (
        f"Sacrifice **two** of your {settings.plural_collectible_name} to forge a new card "
        f"with the **{emoji} {MERGE_SPECIAL_NAME}** special.\n\n"
        "▸ The result keeps one of your parent club types\n"
        "▸ Both inputs are consumed forever\n"
        "▸ Stats roll new ATK/HP bonuses"
    )


class MergeInstanceSelect(discord.ui.Select):
    def __init__(
        self, owner_id: int, *, slot: str, instances: list[BallInstance], placeholder: str, first_id: int | None = None
    ):
        self.owner_id = owner_id
        self.slot = slot
        self.first_id = first_id
        options = [
            discord.SelectOption(
                label=f"#{instance.pk:0X}"[:100], value=str(instance.pk), description=instance.short_description()[:100]
            )
            for instance in instances[:25]
        ]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This forge is private to you.", ephemeral=True)
            return
        instance_id = int(self.values[0])
        bot = cast("BallsDexBot", interaction.client)
        if self.slot == "first":
            layout = await build_merge_menu(bot, self.owner_id, step="pick_second", first_id=instance_id)
        else:
            layout = await build_merge_menu(
                bot, self.owner_id, step="confirm", first_id=self.first_id, second_id=instance_id
            )
        await interaction.response.edit_message(view=layout)


class MergeInstanceSelectRow(ActionRow):
    def __init__(
        self, owner_id: int, *, slot: str, instances: list[BallInstance], placeholder: str, first_id: int | None = None
    ):
        super().__init__()
        self.add_item(
            MergeInstanceSelect(owner_id, slot=slot, instances=instances, placeholder=placeholder, first_id=first_id)
        )


class MergeConfirmRow(ActionRow):
    def __init__(self, owner_id: int, first_id: int, second_id: int):
        super().__init__()
        self.owner_id = owner_id
        self.first_id = first_id
        self.second_id = second_id

    @button(label="Forge merge", style=discord.ButtonStyle.success, emoji="✨")
    async def confirm_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This forge is private to you.", ephemeral=True)
            return
        bot = cast("BallsDexBot", interaction.client)
        await interaction.response.defer()
        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        first = await BallInstance.objects.aget(pk=self.first_id)
        second = await BallInstance.objects.aget(pk=self.second_id)
        try:
            await validate_merge_pair(player, first, second)
            _, summary, card_file = await execute_merge(player, first, second, guild_id=interaction.guild_id, bot=bot)
        except MergeValidationError as exc:
            layout = await build_merge_menu(
                bot,
                self.owner_id,
                step="confirm",
                first_id=self.first_id,
                second_id=self.second_id,
                notice=f"❌ {exc.message}",
            )
            await interaction.edit_original_response(view=layout)
            return

        layout = await build_merge_menu(bot, self.owner_id, step="done", notice=summary)
        await interaction.edit_original_response(view=layout, attachments=[card_file])

    @button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This forge is private to you.", ephemeral=True)
            return
        bot = cast("BallsDexBot", interaction.client)
        layout = await build_merge_menu(bot, self.owner_id, step="intro")
        await interaction.response.edit_message(view=layout)


class MergeNavRow(ActionRow):
    def __init__(self, owner_id: int):
        super().__init__()
        self.owner_id = owner_id

    @button(label="Start forge", style=discord.ButtonStyle.primary, emoji="✨")
    async def start_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This forge is private to you.", ephemeral=True)
            return
        bot = cast("BallsDexBot", interaction.client)
        layout = await build_merge_menu(bot, self.owner_id, step="pick_first")
        await interaction.response.edit_message(view=layout)

    @button(label="Reset", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def reset_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This forge is private to you.", ephemeral=True)
            return
        bot = cast("BallsDexBot", interaction.client)
        layout = await build_merge_menu(bot, self.owner_id, step="intro")
        await interaction.response.edit_message(view=layout)


async def build_merge_menu(
    bot: BallsDexBot,
    owner_id: int,
    *,
    step: str = "intro",
    first_id: int | None = None,
    second_id: int | None = None,
    notice: str = "",
) -> LayoutView:
    player, _ = await Player.objects.aget_or_create(discord_id=owner_id)
    layout = LayoutView(timeout=300)
    container = Container()

    title = "# ✨ FCDex merge forge"
    if notice:
        title = f"{notice}\n\n{title}"

    if step == "intro":
        container.add_item(TextDisplay(truncate_text(f"{title}\n-# {await build_merge_intro_text()}")))
        container.add_item(Separator())
        container.add_item(MergeNavRow(owner_id))
    elif step == "pick_first":
        instances = await load_mergeable_instances(player)
        body = "### Step 1 · First sacrifice\n" + (
            f"Pick a {settings.collectible_name} below." if instances else "*You have no mergeable cards.*"
        )
        container.add_item(TextDisplay(truncate_text(f"{title}\n-# {body}")))
        if instances:
            container.add_item(Separator())
            container.add_item(
                MergeInstanceSelectRow(
                    owner_id, slot="first", instances=instances, placeholder="Choose your first card…"
                )
            )
        container.add_item(Separator())
        container.add_item(MergeNavRow(owner_id))
    elif step == "pick_second":
        instances = await load_mergeable_instances(player, exclude_id=first_id)
        first = await BallInstance.objects.aget(pk=first_id) if first_id else None
        first_label = await format_instance(first) if first else "—"
        body = f"### Step 2 · Second sacrifice\nFirst pick · `{first_label}`\n\n" + (
            "Choose another card." if instances else "*No other mergeable cards available.*"
        )
        container.add_item(TextDisplay(truncate_text(f"{title}\n-# {body}")))
        if instances:
            container.add_item(Separator())
            container.add_item(
                MergeInstanceSelectRow(
                    owner_id,
                    slot="second",
                    instances=instances,
                    placeholder="Choose your second card…",
                    first_id=first_id,
                )
            )
        container.add_item(Separator())
        container.add_item(MergeNavRow(owner_id))
    elif step == "confirm" and first_id and second_id:
        first = await BallInstance.objects.aget(pk=first_id)
        second = await BallInstance.objects.aget(pk=second_id)
        first_label = await format_instance(first)
        second_label = await format_instance(second)
        special = await get_merge_special()
        emoji = special.emoji or "✨"
        body = (
            f"### Confirm merge\n"
            f"**{first_label}** + **{second_label}**\n"
            f"→ **{emoji} {MERGE_SPECIAL_NAME}** forged card\n"
            f"-# Both inputs will be deleted."
        )
        container.add_item(TextDisplay(truncate_text(f"{title}\n-# {body}")))
        container.add_item(Separator())
        container.add_item(MergeConfirmRow(owner_id, first_id, second_id))
        container.add_item(MergeNavRow(owner_id))
    elif step == "done":
        container.add_item(TextDisplay(truncate_text(f"{title}\n-# Forge another pair with **Start forge**.")))
        container.add_item(Separator())
        container.add_item(MergeNavRow(owner_id))
    else:
        container.add_item(TextDisplay(truncate_text(f"{title}\n-# Something went wrong — tap **Reset**.")))
        container.add_item(Separator())
        container.add_item(MergeNavRow(owner_id))

    layout.add_item(container)
    return layout
