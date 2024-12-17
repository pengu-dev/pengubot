import sys
import discord
from discord.ext import commands
import json
import os
import time
import dotenv
import psutil
import io
import contextlib
import textwrap
import traceback

dotenv.load_dotenv()


class MyBot(commands.Bot):  # Subclass commands.Bot
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = self.load_config()
        self.token = os.environ.get("DISCORD_TOKEN")

    def load_config(self):
        with open("config.json", "r") as f:
            return json.load(f)

    def reload_config(self):
        self.config = self.load_config()
        print("Config reloaded.")


intents = discord.Intents.all()


bot = MyBot(command_prefix="pengu!", intents=intents)
bot.command_prefix = commands.when_mentioned_or("pengu!", bot.config.get("prefix"))
# Get permitted roles from config


def is_donald():
    def predicate(ctx):
        return ctx.message.author.id == 289890066514575360

    return commands.check(predicate)


# On Ready Event
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    # Load initial cogs from config
    for cog in bot.config.get("cogs", []):
        try:
            await bot.load_extension(f"cogs.{cog}")
            print(f"Loaded cog: {cog}")
        except Exception as e:
            print(f"Failed to load cog {cog}: {e}")


@bot.command(hidden=True)
@is_donald()
async def _get_config(ctx):
    """
    Displays the current bot configuration.

    This command shows the key-value pairs in the `config.json` file, which controls various aspects of the bot's behavior. The configuration is displayed in a readable JSON format within an embed.

    Note: The bot's token is hidden for security reasons.
    """
    config_copy = bot.config.copy()  # Create a copy of the config
    await ctx.send(
        embed=discord.Embed(
            title="Config",
            description=f"```json\n{json.dumps(config_copy, indent=4)}\n```",
            color=discord.Color.blue(),
        )
    )


@bot.command(hidden=True)
@is_donald()
async def _upload_config(ctx):
    """
    Uploads a new configuration file to update the bot's settings.

    This command allows you to replace the entire `config.json` file with a new one, effectively updating multiple configuration settings at once.

    To use this command:
        1. Attach the new `config.json` file to your message.
        2. Send the message with the command `pengu!upload_config`.

    The bot will then:
        1. Rename the current `config.json` to `backup_config.json` as a precaution.
        2. Save the attached file as the new `config.json`.
        3. Reload the configuration, applying the new settings.
    """
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.filename == "config.json":
            try:
                # Rename old config as backup
                os.rename("config.json", "backup_config.json")
                # Save the new config
                await attachment.save("config.json")
                # Reload config
                bot.reload_config()
                permitted_roles = bot.config.get(
                    "permitted_roles", []
                )  # Update permitted roles
                await ctx.send(
                    embed=discord.Embed(
                        title="Success",
                        description="Config updated!",
                        color=discord.Color.green(),
                    )
                )
                permitted_roles = bot.config.get(
                    "permitted_roles", []
                )  # Update permitted roles
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
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description="Please upload a file named 'config.json'",
                    color=discord.Color.red(),
                )
            )
    else:
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description="No file attached.",
                color=discord.Color.red(),
            )
        )

        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description="No file attached.",
                color=discord.Color.red(),
            )
        )


# Cog Management Commands
@bot.command(hidden=True)
@is_donald()
async def _load(ctx, cog: str):
    """
    Loads a cog (a module with commands) into the bot.

    Cogs are essentially collections of commands that can be loaded or unloaded dynamically without restarting the bot. This command loads a cog from the `cogs` directory, making its commands available for use.

    Arguments:
        cog: The name of the cog file (without the '.py' extension).

    Example usage:
        pengu!load moderation  (This loads the cog from 'cogs/moderation.py')
    """
    try:
        await bot.load_extension(f"cogs.{cog}")
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Loaded cog: {cog}",
                color=discord.Color.green(),
            )
        )
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Loaded cog: {cog}",
                color=discord.Color.green(),
            )
        )
    except Exception as e:
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Failed to load cog: {e}",
                color=discord.Color.red(),
            )
        )


@bot.command(hidden=True)
@is_donald()
async def _unload(ctx, cog: str):
    """
    Unloads a cog from the bot.

    This command unloads a previously loaded cog, making its commands unavailable.

    Arguments:
        cog: The name of the cog file (without the '.py' extension).

    Example usage:
        pengu!unload moderation  (This unloads the cog from 'cogs/moderation.py')
    """
    try:
        await bot.unload_extension(f"cogs.{cog}")
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Unloaded cog: {cog}",
                color=discord.Color.green(),
            )
        )
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Unloaded cog: {cog}",
                color=discord.Color.green(),
            )
        )
    except Exception as e:
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Failed to unload cog: {e}",
                color=discord.Color.red(),
            )
        )


@bot.command(hidden=True)
@is_donald()
async def _reload(ctx, cog: str):
    """
    Reloads a cog, updating its code and commands.

    This command is useful for applying changes you've made to a cog's code without restarting the entire bot. It unloads and then reloads the cog, effectively refreshing its functionality.

    Arguments:
        cog: The name of the cog file (without the '.py' extension).

    Example usage:
        pengu!reload moderation  (This reloads the cog from 'cogs/moderation.py')
    """
    try:
        await bot.reload_extension(f"cogs.{cog}")
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Reloaded cog: {cog}",
                color=discord.Color.green(),
            )
        )
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Reloaded cog: {cog}",
                color=discord.Color.green(),
            )
        )
    except Exception as e:
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Failed to reload cog: {e}",
                color=discord.Color.red(),
            )
        )


@bot.command(hidden=True)
@is_donald()  # Apply permission check
async def _delete_cog(ctx, cog: str):
    """
    Deletes a cog file from the bot's directory.

    This command permanently removes a cog file from the `cogs` directory, effectively deleting its code and associated commands. It also removes the cog from the `config.json` file to prevent the bot from trying to load it in the future.

    Arguments:
        cog: The name of the cog file (without the '.py' extension).

    Example usage:
        pengu!delete_cog moderation  (This deletes 'cogs/moderation.py')

    Warning: This action is irreversible. Make sure you have a backup of the cog file if you might need it later.
    """
    try:
        cog_filename = f"{cog}.py"
        cog_filepath = f"cogs/{cog_filename}"
        os.remove(cog_filepath)

        # Remove cog from config.json
        with open("config.json", "r") as f:
            config = json.load(f)

        if cog in config["cogs"]:
            config["cogs"].remove(cog)
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)

        bot.reload_config()
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Deleted cog: {cog}",
                color=discord.Color.green(),
            )
        )
        await ctx.send(
            embed=discord.Embed(
                title="Success",
                description=f"Deleted cog: {cog}",
                color=discord.Color.green(),
            )
        )
    except Exception as e:
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Failed to delete cog: {e}",
                color=discord.Color.red(),
            )
        )
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Failed to delete cog: {e}",
                color=discord.Color.red(),
            )
        )


@bot.command(hidden=True)
@is_donald()  # Apply permission check
async def _upload_cog(ctx):
    """
    Uploads a new cog file to the bot.

    This command allows you to add new commands or functionality to the bot by uploading a Python file containing a cog definition. The uploaded file will be saved in the `cogs` directory, and the cog will be automatically added to the `config.json` file so that it's loaded when the bot starts.

    To use this command:
        1. Attach the cog file (with the '.py' extension) to your message.
        2. Send the message with the command `pengu!upload_cog`.

    The bot will then:
        1. Save the attached file in the `cogs` directory.
        2. Add the cog's name to the `cogs` array in `config.json`.
    """
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.filename.endswith(".py"):
            try:
                cog_name = attachment.filename[:-3]  # Remove .py extension
                await attachment.save(f"cogs/{attachment.filename}")

                # Add cog to config.json
                with open("config.json", "r") as f:
                    config = json.load(f)

                if cog_name not in config["cogs"]:
                    config["cogs"].append(cog_name)
                    with open("config.json", "w") as f:
                        json.dump(config, f, indent=4)

                bot.reload_config()
                await ctx.send(
                    embed=discord.Embed(
                        title="Success",
                        description=f"Uploaded cog: {attachment.filename}",
                        color=discord.Color.green(),
                    )
                )
                await ctx.send(
                    embed=discord.Embed(
                        title="Success",
                        description=f"Uploaded cog: {attachment.filename}",
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
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description="Please upload a Python file (.py)",
                    color=discord.Color.red(),
                )
            )
    else:
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description="No file attached.",
                color=discord.Color.red(),
            )
        )


@bot.command(hidden=True)
@is_donald()
async def _create_cog(ctx, cog_name: str):
    """
    Creates a new cog file with boilerplate code.

    This command generates a basic cog file with a simple example command. The generated file is saved in the `cogs` directory and sent to the channel as an attachment. The cog is also added to the `config.json` file, so it will be loaded when the bot starts.

    Arguments:
        cog_name: The name you want to give to the new cog (without the '.py' extension).

    Example usage:
        pengu!create_cog my_new_cog

    This will create a file named `my_new_cog.py` in the `cogs` directory, add "my_new_cog" to the `config.json`, and send the file contents in the chat.
    """
    cog_filename = f"{cog_name}.py"
    cog_filepath = f"cogs/{cog_filename}"

    # Check if cog already exists
    if os.path.exists(cog_filepath):
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Cog '{cog_name}' already exists.",
                color=discord.Color.red(),
            )
        )
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Cog '{cog_name}' already exists.",
                color=discord.Color.red(),
            )
        )
        return

    # Boilerplate cog code
    boilerplate = f"""import discord
from discord.ext import commands

class {cog_name}(commands.Cog):
    def ___init__(self, bot):
        self.bot = bot

    @commands.command()
    async def _example(self, ctx):
        await ctx.send(embed=discord.Embed(title="Example", description="This is an example command from the {cog_name} cog.", color=discord.Color.blue()))

async def _setup(bot):
    await bot.add_cog({cog_name}(bot))
"""

    try:
        # Create the cog file
        with open(cog_filepath, "w") as f:
            f.write(boilerplate)

        with open("config.json", "r") as f:
            config = json.load(f)

        if cog_name not in config["cogs"]:
            config["cogs"].append(cog_name)
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)

        bot.reload_config()
        # Send the cog file as an attachment
        with open(cog_filepath, "rb") as f:
            await ctx.send(
                embed=discord.Embed(
                    title="Success",
                    description=f"Created cog '{cog_name}'.",
                    color=discord.Color.green(),
                )
            )
            await ctx.send(
                embed=discord.Embed(
                    title="Success",
                    description=f"Created cog '{cog_name}'.",
                    color=discord.Color.green(),
                )
            )
            await ctx.send(file=discord.File(f, filename=cog_filename))
    except Exception as e:
        await ctx.send(
            embed=discord.Embed(
                title="Error",
                description=f"Failed to create cog: {e}",
                color=discord.Color.red(),
            )
        )


# Bot Info Command
@bot.command(hidden=True)
@is_donald()
async def botinfo(ctx):
    """
    Shows detailed information about the bot's current status.

    This command provides various statistics and information about the bot, including:

    * Uptime: How long the bot has been running since its last restart.
    * Memory Usage: The amount of RAM the bot is currently using.
    * Cogs Loaded: A list of the cogs that are currently loaded and active.
    * Prefix: The current prefix used to invoke the bot's commands.
    """
    uptime = int(time.time() - bot.start_time)
    memory_usage = psutil.Process().memory_full_info().rss / 1024**2  # in MB
    cogs_loaded = ", ".join(bot.extensions.keys())

    # Get available cogs (not loaded)
    all_cogs = [f[:-3] for f in os.listdir("cogs") if f.endswith(".py")]
    available_cogs = set(all_cogs) - set(bot.extensions.keys())

    embed = discord.Embed(title="Bot Information", color=discord.Color.blue())
    embed.add_field(name="Uptime", value=f"{uptime} seconds")
    embed.add_field(name="Memory Usage", value=f"{memory_usage:.2f} MB")
    embed.add_field(name="Cogs Loaded", value=cogs_loaded or "None")
    embed.add_field(
        name="Prefixes",
        value=f'`{bot.config.get("prefix")}`\n`pengu!`\n<@{bot.user.id}>',
    )
    embed.add_field(name="Available Cogs", value=", ".join(available_cogs) or "None")
    embed.add_field(name="Latency", value=f"{bot.latency * 1000:.2f} ms")
    embed.add_field(
        name="Python Version",
        value=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    embed.add_field(name="Discord.py Version", value=discord.__version__)
    embed.add_field(name="Guild Count", value=f"{len(bot.guilds)}")
    embed.add_field(name="User Count", value=f"{len(bot.users)}")

    # Add more fields as needed (e.g., latency, etc.)
    await ctx.send(embed=embed)


if __name__ == "__main__":
    # Start the bot
    bot.start_time = time.time()  # Record start time
    bot.run(bot.token)
