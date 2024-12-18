from typing import Optional, Union
import discord
from discord.ext import commands
import difflib
from .utils import checks
from discord import ButtonStyle, app_commands, Interaction, SelectOption


class CancelButton(discord.ui.Button):
    def __init__(self, original_message):
        super().__init__(style=ButtonStyle.danger, label=":x:")
        self.original_message = original_message

    async def callback(self, interaction: Interaction):
        await self.original_message.delete()
        await interaction.response.send_message(
            "Tag selection cancelled.", ephemeral=True
        )


class TagButton(discord.ui.Button):
    def __init__(
        self, tag_name: str, database, guild_id, original_message, bot_message
    ):
        super().__init__(style=ButtonStyle.primary, label=tag_name)
        self.tag_name = tag_name
        self.database = database
        self.guild_id = guild_id
        self.original_message = original_message
        self.bot_message = bot_message

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.database.add_count(self.guild_id, self.tag_name)
        tag_content = await self.database.get_tag(self.guild_id, self.tag_name)
        await self.original_message.delete()
        await self.bot_message.delete()
        await interaction.followup.send(tag_content)


class TagButtons(discord.ui.View):
    def __init__(self, ctx, closest_matches, database, bot_message):
        super().__init__()
        self.timeout = None
        self.ctx = ctx
        self.database = database
        self.original_message = ctx.message
        self.bot_message = bot_message
        for match in closest_matches:
            self.add_item(
                TagButton(
                    match,
                    database,
                    ctx.guild.id,
                    self.original_message,
                    self.bot_message,
                )
            )
        self.add_item(CancelButton(self.original_message))  # Add the Cancel button

    async def on_timeout(self):
        await self.ctx.send("Tag selection timed out.")
        await self.bot_message.delete()


class TagSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database = self.bot.get_cog("Database")

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, name: str):
        """Displays a tag."""
        tag_content = await self.database.get_tag(ctx.guild.id, name)
        if tag_content:
            await self.database.add_count(ctx.guild.id, name)
            await ctx.send(tag_content)
        else:
            # Autocorrection with buttons
            all_tags = await self.database.get_all_tags(ctx.guild.id)
            closest_matches = difflib.get_close_matches(name, all_tags, n=5, cutoff=0.5)

            if closest_matches:
                question_message = await ctx.send(
                    f"Tag '{name}' not found. Did you mean one of these?"
                )
                view = TagButtons(ctx, closest_matches, self.database, question_message)
                await question_message.edit(view=view)
            else:
                await ctx.send(f"Tag '{name}' not found.")

    @tag.command(name="create", description="Creates a new tag.")
    async def tag_create(
        self,
        ctx,
        name: str,
        message_ref: Optional[Union[discord.Message, str]] = None,
        *,
        content: str = None,
    ):
        """Creates a new tag.
        You can provide a message ID or reply to a message to use its content.
        """

        if isinstance(message_ref, discord.Message):
            content = message_ref.content
        elif isinstance(message_ref, str):
            try:
                message = await ctx.fetch_message(int(message_ref))
                content = message.content
            except discord.NotFound:
                return await ctx.send("Message not found.")
            except ValueError:
                return await ctx.send("Invalid message ID.")
        elif content is None and ctx.message.reference:
            try:
                replied_message = await ctx.fetch_message(
                    ctx.message.reference.message_id
                )
                content = replied_message.content
            except discord.NotFound:
                return await ctx.send("Replied message not found.")

        if content is None:
            return await ctx.send(
                "Please provide content for the tag or reply to a message."
            )

        try:
            await self.database.create_tag(ctx.guild.id, name, content)
            await ctx.send(f"Tag '{name}' created successfully.")
        except Exception as e:  # Consider using a more specific exception type
            await ctx.send(f"Error creating tag: {e}")

    @tag.command(name="edit")
    @checks.is_mod()
    async def tag_edit(self, ctx, name: str, *, content: str):
        """Edits an existing tag."""
        try:
            await self.database.edit_tag(ctx.guild.id, name, content)
            await ctx.send(f"Tag '{name}' edited successfully.")
        except Exception as e:
            await ctx.send(f"Error editing tag: {e}")

    @tag.command(name="delete")
    @checks.is_mod()
    async def tag_delete(self, ctx, name: str):
        """Deletes a tag."""
        try:
            await self.database.remove_tag(ctx.guild.id, name)
            await ctx.send(f"Tag '{name}' deleted successfully.")
        except Exception as e:
            await ctx.send(f"Error deleting tag: {e}")

    @tag.command(name="list", description="Lists the most used tags.")
    async def tag_list(
        self, ctx
    ):  # sourcery skip: for-append-to-extend, list-comprehension
        """Lists the top 20 most used tags."""
        result = await self.database.run_query(
            """
            SELECT name, use_count FROM tags 
            WHERE guild_id = ?
            ORDER BY use_count DESC 
            LIMIT 20
            """,
            (ctx.guild.id,),
            fetch=True,
        )

        if not result:
            return await ctx.send("No tags found in this server.")

        tag_list = []
        for i, (name, count) in enumerate(result, 1):  # Start enumerate from 1
            tag_list.append(f"{i}. `{name}` — {count}")

        await ctx.send("**## Most Used Tags:**" + "\n".join(tag_list))


async def setup(bot):
    await bot.add_cog(TagSystem(bot))
