from contextlib import redirect_stdout
import io
import json
import os
import shutil
import textwrap
import traceback
import aiohttp
import discord
from discord.ext import commands
from .utils import checks
from typing import Optional, Any


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_result: Optional[Any] = None

    @commands.command(name="upload_cog")
    @checks.is_donald()
    async def upload_cog(self, ctx, directory: str = "cogs"):
        """
        Uploads new cog file(s) to the bot.

        This command allows you to add new commands or functionality to the
        bot by uploading Python files containing cog definitions. The
        uploaded files will be saved in the specified directory, and the
        cogs will be automatically added to the `config.json` file so
        that they're loaded when the bot starts.

        Usage:
           1. Attach the cog file(s) (with the '.py' extension) to your message.
           2. Send the message with the command `!upload_cog [directory]`

        Optional argument:
           directory: The directory to save the cog files to. Defaults to "cogs".

        The bot will then:
           1. Save the attached files in the specified directory.
           2. Add the cogs' names to the `cogs` array in `config.json`.
        """
        if not ctx.message.attachments:
            return await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description="No file attached.",
                    color=discord.Color.red(),
                )
            )

        # Create the directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory)

        for attachment in ctx.message.attachments:
            if attachment.filename.endswith(".py"):
                try:
                    cog_name = attachment.filename[:-3]
                    await attachment.save(f"{directory}/{attachment.filename}")

                    # Add cog to config.json
                    with open("config.json", "r") as f:
                        config = json.load(f)

                    if cog_name not in config["cogs"]:
                        config["cogs"].append(cog_name)
                        with open("config.json", "w") as f:
                            json.dump(config, f, indent=4)

                    # You might want to add logic to reload the cog here
                    # self.bot.reload_extension(f"{directory}.{cog_name}")

                    await ctx.send(
                        embed=discord.Embed(
                            title="Success",
                            description=f"Uploaded cog: {attachment.filename} to {directory}",
                            color=discord.Color.green(),
                        )
                    )
                except Exception as e:
                    await ctx.send(
                        embed=discord.Embed(
                            title="Error",
                            description=f"Failed to upload cog: {e}",
                            color=discord.Color.red(),
                        )
                    )
            else:
                await ctx.send(
                    embed=discord.Embed(
                        title="Error",
                        description="Please upload a Python file (.py)",
                        color=discord.Color.red(),
                    )
                )

    @commands.command(name="load")
    @checks.is_donald()
    async def load_cog(self, ctx, cog: str):
        """Loads a cog."""
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            await ctx.send(f"Loaded cog: {cog}")
        except Exception as e:
            await ctx.send(f"Error loading cog: {cog}\n{e}")

    @commands.command(name="unload")
    @checks.is_donald()
    async def unload_cog(self, ctx, cog: str):
        """Unloads a cog."""
        try:
            self.bot.unload_extension(f"cogs.{cog}")
            await ctx.send(f"Unloaded cog: {cog}")
        except Exception as e:
            await ctx.send(f"Error unloading cog: {cog}\n{e}")

    @commands.command(name="reload")
    @checks.is_donald()
    async def reload_cog(self, ctx, cog: str):
        """Reloads a cog."""
        if cog == "*":  # Reload all cogs
            reloaded = []
            for filename in self.bot.config["cogs"]:
                try:
                    await self.bot.reload_extension(f"cogs.{filename}")
                    reloaded.append(f"* `{filename}`")
                except Exception as e:
                    await ctx.send(f"Error reloading cog: {filename}\n{e}")
            await ctx.send("Reloaded all cogs:\n-# " + "\n-# ".join(reloaded))
        else:
            try:
                await self.bot.reload_extension(f"cogs.{cog}")
                await ctx.send(f"Reloaded cog: {cog}")
            except Exception as e:
                await ctx.send(f"Error reloading cog: {cog}\n{e}")

    @commands.command(name="delete_cog")
    @checks.is_donald()
    async def delete_cog(self, ctx, cog: str):
        """Deletes a cog file."""
        try:
            os.remove(f"cogs/{cog}.py")  # Make sure to delete the correct file
            with open("config.json", "r") as f:
                config = json.load(f)

            if cog in config["cogs"]:
                config["cogs"].remove(cog)
                with open("config.json", "w") as f:
                    json.dump(config, f, indent=4)
            await ctx.send(f"Deleted cog: {cog}")
        except Exception as e:
            await ctx.send(f"Error deleting cog: {cog}\n{e}")

    def cleanup_code(self, content: str) -> str:
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        # remove `foo`
        return content.strip("` \n")

    @commands.command(hidden=True, name="eval")
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code"""

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "_": self._last_result,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f"```py\n{value}{traceback.format_exc()}\n```")
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("\u2705")
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f"```py\n{value}\n```")
            else:
                self._last_result = ret
                await ctx.send(f"```py\n{value}{ret}\n```")

    @commands.command()
    @checks.is_donald()
    async def get_config(self, ctx):
        """
        Displays the current bot configuration.

        This command shows the key-value pairs in the `config.json` file, which controls various aspects of the bot's behavior. The configuration is displayed in a readable JSON format within an embed.

        Note: The bot's token is hidden for security reasons.
        """
        config_copy = self.bot.config.copy()  # Create a copy of the config
        await ctx.send(
            embed=discord.Embed(
                title="Config",
                description=f"```json\n{json.dumps(config_copy, indent=4)}\n```",
                color=discord.Color.blue(),
            )
        )

    @commands.command(name="upload_config")
    @checks.is_donald()
    async def upload_config(self, ctx):
        """
        Uploads a new configuration file to update the bot's settings.

        This command allows you to replace the entire `config.json` file
        with a new one, effectively updating multiple configuration
        settings at once.

        To use this command:
           1. Attach the new `config.json` file to your message.
           2. Send the message with the command `!upload_config`.

        The bot will then:
           1. Rename the current `config.json` to `backup_config.json`
              as a precaution.
           2. Save the attached file as the new `config.json`.
           3. Reload the configuration, applying the new settings.
        """
        if not ctx.message.attachments:
            return await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description="No file attached.",
                    color=discord.Color.red(),
                )
            )

        attachment = ctx.message.attachments[0]
        if attachment.filename == "config.json":
            try:
                # Rename old config as backup
                os.rename("config.json", "backup_config.json")
                # Save the new config
                await attachment.save("config.json")
                # Reload config (assuming you have a reload_config function in your bot)
                self.bot.reload_config()
                await ctx.send(
                    embed=discord.Embed(
                        title="Success",
                        description="Config updated!",
                        color=discord.Color.green(),
                    )
                )
            except Exception as e:
                await ctx.send(
                    embed=discord.Embed(
                        title="Error",
                        description=f"Failed to update config: {e}",
                        color=discord.Color.red(),
                    )
                )
        else:
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description="Please upload a file named 'config.json'",
                    color=discord.Color.red(),
                )
            )

    @commands.command(name="pull-repo")
    @checks.is_donald()
    async def update_from_repo(self, ctx, branch: str = "master", repo_url=None):
        """
        Updates cogs and utils from a GitHub repository.

        This command pulls the 'cogs' folder and 'cogs/utils' folder
        from the specified GitHub repository and updates the
        corresponding files in the bot's directory.

        Args:
            branch:str      — Defaults to master
            repo_url:str    — Defaults to https://github.com/pengu-dev/pengubot

        Usage:
            !pull-repo <branch> <repo_url>

        Example:
            !pull-repo dev https://github.com/your-username/your-repo
        """
        try:
            if repo_name is None:
                repo_name = "https://github.com/pengu-dev/pengubot"
            # Extract the repository name from the URL
            repo_name = repo_url.split("/")[-1]

            async with aiohttp.ClientSession() as session:
                # Download the cogs folder as a zip file
                cogs_url = f"{repo_url}/archive/refs/heads/{branch}.zip"
                async with session.get(cogs_url) as resp:
                    if resp.status == 200:
                        zip_data = await resp.read()
                        with open("temp_cogs.zip", "wb") as f:
                            f.write(zip_data)

            # Extract the zip file
            shutil.unpack_archive("temp_cogs.zip", "temp_cogs")

            # Copy the cogs and utils folders
            source_cogs_folder = f"temp_cogs/{repo_name}-{branch}/cogs"
            source_utils_folder = f"temp_cogs/{repo_name}-{branch}/cogs/utils"
            if os.path.exists(source_cogs_folder):
                shutil.rmtree("cogs", ignore_errors=True)  # Remove existing cogs folder
                shutil.copytree(source_cogs_folder, "cogs")
                if os.path.exists(source_utils_folder):
                    shutil.rmtree(
                        "cogs/utils", ignore_errors=True
                    )  # Remove existing utils folder
                    shutil.copytree(source_utils_folder, "cogs/utils")
                await ctx.send(
                    embed=discord.Embed(
                        title="Success",
                        description="Cogs and utils updated from the repository!",
                        color=discord.Color.green(),
                    )
                )
            else:
                await ctx.send(
                    embed=discord.Embed(
                        title="Error",
                        description="Cogs folder not found in the repository.",
                        color=discord.Color.red(),
                    )
                )

            # Clean up temporary files
            os.remove("temp_cogs.zip")
            shutil.rmtree("temp_cogs")

            # Reload all cogs (optional, but recommended)
            await self.reload_all_cogs(ctx)

        except Exception as e:
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"Failed to update from repository: {e}",
                    color=discord.Color.red(),
                )
            )

    async def reload_all_cogs(self, ctx):
        """Reloads all cogs."""

        async def load_or_reload(self, ctx, cog_name):
            if f"cogs.{cog_name}" in self.bot.extensions:
                await self.bot.load_extension(f"cogs.{cog_name}")
            else:
                await self.bot.reload_extension(f"cogs.{cog_name}")

        # Add new cogs to config.json
        with open("config.json", "r") as f:
            config = json.load(f)

        for filename in os.listdir("cogs"):
            cog_name = filename[:-3]
            if filename.endswith(".py"):
                try:
                    if cog_name not in config["cogs"]:
                        config["cogs"].append(cog_name)
                    await self.load_or_reload(ctx, cog_name)
                except Exception as e:
                    await ctx.send(f"Error reloading cog: {cog_name}\n{e}")

        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        self.bot.reload_config()
        await ctx.send("Reloaded all cogs.")


async def setup(bot):
    await bot.add_cog(Admin(bot))
