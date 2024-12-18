from __future__ import annotations
from discord.ext import commands
from discord.ext import commands

DONALD_ID = 289890066514575360
LC_SERVER_ID = 870142583668629524
MC_SERVER_ID = 1318364025905479690


def is_donald():  # More descriptive name
    """Check if the user is the bot owner (Donald)."""

    async def predicate(ctx: commands.Context):
        if ctx.author.id == DONALD_ID:
            return True
        else:
            raise commands.CheckFailure(
                "You must be **The Penguin** to use this command."
            )

    return commands.check(predicate)


def is_mod():
    """Check if the user has moderator permissions or is the bot owner."""

    async def predicate(ctx: commands.Context):
        is_moderator = (
            ctx.author.guild_permissions.manage_messages
            and ctx.author.guild_permissions.kick_members
        )
        if not is_moderator or ctx.author.id != DONALD_ID:
            raise commands.CheckFailure(
                "You need the following permissions to use this command: `manage_members`, `kick_members`"
            )
        return True

    return commands.check(predicate)


def is_admin():
    """Checks if the user has manage_channels permissions or is the bot owner"""

    async def predicate(ctx: commands.Context):
        is_admin = ctx.author.guild_permissions.manage_channels
        if not is_admin or ctx.author.id != DONALD_ID:
            raise commands.CheckFailure(
                "You need the following permissions to use this command: `manage_members`, `kick_members`"
            )
        return True

    return commands.check(predicate)


def in_mc():
    """Checks if the command is being used in the Minecraft Discord Server"""

    async def predicate(ctx: commands.Context):
        if ctx.author.id == DONALD_ID:
            return True
        if ctx.guild.id != MC_SERVER_ID:
            raise commands.CheckFailure(
                "This command is only usable in the Lewd Corner Minecraft Discord Server."
            )
        return True

    return commands.check(predicate)


def in_lc():
    """Check if the command is being used in the Lewd Corner Discord Server"""

    async def predicate(ctx: commands.Context):
        if ctx.author.id == DONALD_ID:
            return True
        if ctx.guild.id != LC_SERVER_ID:
            raise commands.CheckFailure(
                "This command is only usable in the Lewd Corner Discord Server."
            )
        return True

    return commands.check(predicate)
