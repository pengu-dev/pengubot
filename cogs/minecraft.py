import contextlib
import datetime
import discord
from rcon.source import Client
from discord.ext import commands
from .utils import checks


class rcon_client:
    def __init__(self, bot, address, port, password):
        self.address = address
        self.port = port
        self.password = password
        self.bot = bot
        self.database = self.bot.get_cog("Database")

    def _send_command(self, *args):
        with Client(self.address, self.port, passwd=self.password) as client:
            try:
                response = client.run(*args)
            except ConnectionError:
                print("Failed to connect to RCON server")
                return "Failed to connect to RCON server"
            except TimeoutError:
                print("Connection timed out while sending command")
                return "Connection timed out while sending command"
            except Exception as e:  # Catch remaining unexpected exceptions
                print(f"Internal RCON error occurred: {str(e)}")
                return "An unexpected error occurred while executing the command"

            # Check if the response indicates an error (adjust as needed)
            if isinstance(response, str) and response.startswith("Error executing:"):
                return response

            return response

    def whitelist_get(self):
        return self._send_command("whitelist", "list")

    def whitelist_add(self, username):
        return self._send_command("whitelist", "add", username)

    def whitelist_remove(self, username):
        return self._send_command("whitelist", "remove", username)

    def whitelist_on(self):
        return self._send_command("whitelist", "on")

    def whitelist_off(self):
        return self._send_command("whitelist", "off")

    def whitelist_reload(self):
        return self._send_command("whitelist", "reload")

    def ban(self, username):
        return self._send_command("ban", username)

    def pardon(self, username):
        """Pardons a banned player."""
        return self._send_command("pardon", username)

    def ban_ip(self, ip_address):
        """Bans an IP address from the server."""
        return self._send_command("ban-ip", ip_address)

    def pardon_ip(self, ip_address):
        """Pardons a banned IP address."""
        return self._send_command("pardon-ip", ip_address)

    def kick(self, username, reason=None):
        """Kicks a player from the server."""
        if reason:
            return self._send_command("kick", username, reason)
        else:
            return self._send_command("kick", username)

    def op(self, username):
        """Gives operator status to a player."""
        return self._send_command("op", username)

    def deop(self, username):
        """Removes operator status from a player."""
        return self._send_command("deop", username)

    def gamemode(self, gamemode, username=None):
        """Sets the game mode for a player or the server."""
        if username:
            return self._send_command("gamemode", gamemode, username)
        else:
            return self._send_command("gamemode", gamemode)

    def difficulty(self, difficulty):
        """Sets the difficulty level of the server."""
        return self._send_command("difficulty", difficulty)

    def time(self, time):
        """Sets the time of day in the server."""
        return self._send_command("time", "set", time)

    def give(self, username, item, amount=1):
        """Gives an item to a player."""
        return self._send_command("give", username, item, amount)

    def teleport(self, username, destination):
        """Teleports a player to a specified location or another player."""
        return self._send_command("tp", username, destination)

    def say(self, message):
        """Broadcasts a message to all players on the server."""
        try:
            message = message.strip()
            if not message:
                return "Error: Cannot send an empty message."

            json_payload = str(
                {"text": f"[Server] {message}", "color": "green"}
            ).replace("'", '"')
            return self._send_command("tellraw", "@a", json_payload)

        except Exception as e:
            print(f"Error sending message: {e}")
            return "Error sending message."


class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.minecraft = rcon_client(
            bot,
            bot.config["minecraft"]["ip"],
            bot.config["minecraft"]["port"],
            bot.config["minecraft"]["password"],
        )
        self.minecraft_discord_server_ip = bot.config["minecraft"]["discord_server_id"]
        self.debug_mode = bot.config["minecraft"]["debug_mode"]
        self.log_channel = bot.get_channel(bot.config["minecraft"]["log_channel_id"])

        self.bypass_cog_check = ["minecraft-join"]

        self.main_server = bot.get_guild(
            586928217768591370 if self.debug_mode else bot.config["main_server_id"]
        )

        self.level_roles = self.get_level_roles()
        self.required_level_to_join = self.bot.config["minecraft"][
            "required_level_to_join"
        ]

    async def send_log(self, title: str, description: str, color: discord.Color):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        # Send DM with embed
        await self.log_channel.send(embed=embed)

    def get_level_roles(self):
        """
        Gets all roles that follow the format '[Level N] Name'
        and stores them in self.level_roles.
        """
        level_roles = {}
        for role in self.main_server.roles:
            with contextlib.suppress(IndexError, ValueError):
                if not role.name.startswith("[Level "):
                    continue  # Skip roles that don't match the format

                level_str = role.name.split("]")[0]  # Get the part before the ']'
                level_number = int(level_str.split("[Level ")[1])  # Extract the number
                level_roles[level_number] = role.id
        return level_roles

    def check_join_requirements(self, user: discord.Member):
        """
        Check if the user meets the required level to join the minecraft server.
        """
        highest_level = 0
        for role in user.roles:
            for level_number, role_id in self.level_roles.items():
                if role.id == role_id and level_number > highest_level:
                    highest_level = level_number

        return highest_level >= self.required_level_to_join

    @commands.group(aliases=["mc"])
    @checks.is_mod()
    @checks.in_mc()
    async def minecraft(self, ctx):
        """Manages the Minecraft server and configuration."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.command(name="minecraft-join")
    @checks.in_lc()
    async def join_command(self, ctx, minecraft_username: str):
        if self.check_join_requirements(ctx.author):
            try:
                # Create buttons
                accept_button = discord.ui.Button(
                    label="Accept", style=discord.ButtonStyle.green
                )
                reject_button = discord.ui.Button(
                    label="Reject", style=discord.ButtonStyle.red
                )

                # Define button callbacks
                async def accept_callback(interaction: discord.Interaction):
                    if interaction.user != ctx.author:
                        await interaction.response.send_message(
                            "You are not authorized to use this button.", ephemeral=True
                        )
                        return

                    try:
                        # Send DM with server info
                        # Create embed for DM
                        embed = discord.Embed(
                            title="Welcome to our Minecraft server!",
                            description=(
                                "We're glad to have you!\n\n"
                                "**Important:** Please read the `#information` and `#rules` channels in our Discord server first.\n"
                                "If you have any questions, don't hesitate to ask in the `#general` channel.\n\n"
                                "Have fun exploring the world!"
                            ),
                            color=discord.Color.green(),
                        )
                        embed.add_field(
                            name="Discord Server Invite",
                            value=self.bot.config["minecraft"]["server_invite_link"],
                        )

                        # Send DM with embed
                        await ctx.author.send(embed=embed)
                        await interaction.response.send_message(
                            "You have been sent a DM with the server information.",
                            ephemeral=True,
                        )
                        await interaction.message.delete()

                    except discord.HTTPException:
                        await interaction.response.send_message(
                            "I couldn't send you a DM. Please check your privacy settings.",
                            ephemeral=True,
                        )
                        await interaction.message.delete()

                async def reject_callback(interaction: discord.Interaction):

                    if interaction.user != ctx.author:
                        await interaction.response.send_message(
                            "You are not authorized to use this button.", ephemeral=True
                        )
                        return

                    await interaction.response.send_message(
                        "I can't invite you to the server without DMing you. Please redo the command and try again.",
                        ephemeral=True,
                    )
                    await interaction.message.delete()

                # Assign callbacks to buttons
                accept_button.callback = accept_callback
                reject_button.callback = reject_callback

                # Create a View to hold the buttons
                view = discord.ui.View()
                view.add_item(accept_button)
                view.add_item(reject_button)

                # Create embed for the question
                embed = discord.Embed(
                    title="You must accept me sending a direct message to you below.",
                    description=(
                        "Double check that you wrote your Minecraft name correctly.\n"
                    ),
                    color=discord.Color.blue(),
                )
                embed.add_field(name="Minecraft Username:", value=minecraft_username)
                embed.add_field(name="Discord ID:", value=ctx.author.id)
                embed.set_footer(
                    text="Press 'Reject' if your information isn't correct and redo the command."
                )
                # Send the embed with buttons
                await ctx.send(embed=embed, view=view)

            except Exception as e:
                await ctx.send(f"An error occurred: {e}")
                await ctx.message.delete()
        else:
            await ctx.send(
                f":no_entry: You do not meet the required level to join the minecraft server. You need to be **Level {self.required_level_to_join}.**\n-# If you think this is a mistake, please contact a Minecraft staff member."
            )

    @minecraft.group(name="run")
    async def run_command(self, ctx, *, args):
        """Runs a command on the Minecraft server."""
        # Remove surrounding quotes if present
        args = args.strip('"')
        response = self.minecraft._send_command(*args.split())
        await self.send_log(
            "Run Command",
            f"{ctx.author.mention} used `run` with args: `{','.join(args.split( ))}`",
            discord.Color.teal(),
        )
        await ctx.send(response)

    @minecraft.command(name="ban")
    async def ban_player(self, ctx, username: str):
        """Bans a player from the Minecraft server."""
        try:
            result = self.minecraft.ban(username)
            await ctx.send(result)
            await self.send_log(
                "Ban Command",
                f"{ctx.author.mention} used `ban` on `{username}`",
                discord.Color.brand_red(),
            )
        except Exception as e:
            await ctx.send(f"Error banning player: {e}")

    @minecraft.command(name="ban-ip")
    async def ban_ip_address(self, ctx, ip_address: str):
        """Bans an IP address from the Minecraft server."""
        try:
            result = self.minecraft.ban_ip(ip_address)
            await ctx.send(result)
            await self.send_log(
                "Ban-IP Command",
                f"{ctx.author.mention} used `ban-ip` on `{ip_address}`",
                discord.Color.brand_red(),
            )
        except Exception as e:
            await ctx.send(f"Error banning IP address: {e}")

    @minecraft.command(name="pardon", aliases=["unban"])
    async def pardon_player(self, ctx, username: str):
        """Pardons a banned player from the Minecraft server."""
        try:
            result = self.minecraft.pardon(username)
            await ctx.send(result)
            await self.send_log(
                "Pardon Command",
                f"{ctx.author.mention} used `pardon` on `{username}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error pardoning player: {e}")

    @minecraft.command(name="pardon-ip")
    async def pardon_ip_address(self, ctx, ip_address: str):
        """Pardons a banned IP address from the Minecraft server."""
        try:
            result = self.minecraft.pardon_ip(ip_address)
            await ctx.send(result)
            await self.send_log(
                "Pardon-IP Command",
                f"{ctx.author.mention} used `pardon-ip` on `{ip_address}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error pardoning IP address: {e}")

    @minecraft.command(name="kick")
    async def kick_player(self, ctx, username: str, *, reason: str = None):
        """Kicks a player from the Minecraft server."""
        try:
            result = self.minecraft.kick(username, reason)
            await ctx.send(result)
            await self.send_log(
                "Kick Command",
                f"{ctx.author.mention} used `kick` on `{username}` with reason: `{reason}`",
                discord.Color.orange(),
            )
        except Exception as e:
            await ctx.send(f"Error kicking player: {e}")

    @minecraft.command(name="op")
    async def op_player(self, ctx, username: str):
        """Gives operator status to a player on the Minecraft server."""
        try:
            result = self.minecraft.op(username)
            await ctx.send(result)
            await self.send_log(
                "Op Command",
                f"{ctx.author.mention} used `op` on `{username}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error giving operator status: {e}")

    @minecraft.command(name="deop")
    async def deop_player(self, ctx, username: str):
        """Removes operator status from a player on the Minecraft server."""
        try:
            result = self.minecraft.deop(username)
            await ctx.send(result)
            await self.send_log(
                "Deop Command",
                f"{ctx.author.mention} used `deop` on `{username}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error removing operator status: {e}")

    @minecraft.command(name="gamemode")
    async def set_gamemode(self, ctx, gamemode: str, username: str = None):
        """Sets the game mode for a player or the Minecraft server."""
        try:
            result = self.minecraft.gamemode(gamemode, username)
            await ctx.send(result)
            await self.send_log(
                "Gamemode Command",
                f"{ctx.author.mention} used `gamemode` on `{username}`, changed gamemode to: `{gamemode}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error setting game mode: {e}")

    @minecraft.command(name="difficulty")
    async def set_difficulty(self, ctx, difficulty: str):
        """Sets the difficulty level of the Minecraft server."""
        try:
            result = self.minecraft.difficulty(difficulty)
            await ctx.send(result)
            await self.send_log(
                "Difficulty Command",
                f"{ctx.author.mention} used `difficulty`, set difficulty to: `{difficulty}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error setting difficulty: {e}")

    @minecraft.command(name="time")
    async def set_time(self, ctx, time: str):
        """Sets the time of day in the Minecraft server."""
        try:
            result = self.minecraft.time(time)
            await ctx.send(result)
            await self.send_log(
                "Time Command",
                f"{ctx.author.mention} used `time`, set time to: `{time}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error setting time: {e}")

    @minecraft.command(name="give")
    async def give_item(self, ctx, username: str, item: str, amount: int = 1):
        """Gives an item to a player on the Minecraft server."""
        try:
            result = self.minecraft.give(username, item, str(amount))
            await ctx.send(result)
            await self.send_log(
                "Give Command",
                f"{ctx.author.mention} used `give` on `{username}`, gave `{amount}` `{item}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error giving item: {e}")

    @minecraft.command(name="teleport", aliases=["tp"])
    async def teleport_player(self, ctx, username: str, *, destination: str):
        """Teleports a player to a specified location or another player."""
        try:
            result = self.minecraft.teleport(username, destination)
            await ctx.send(result)
            await self.send_log(
                "Teleport Command",
                f"{ctx.author.mention} used `teleport` on `{username}`, to: `{destination}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error teleporting player: {e}")

    @minecraft.command(name="say")
    async def say_message(self, ctx, *, message: str):
        """Broadcasts a message to all players on the Minecraft server."""
        try:
            result = self.minecraft.say(message)

            # Check if the result indicates an error
            if isinstance(result, str) and result.startswith(
                "Error:"
            ):  # Or your specific error pattern
                await ctx.send(result)  # Send the error message to Discord
            else:
                await ctx.send(
                    "Message sent to Minecraft server successfully!"
                )  # Or a custom success message
                await ctx.send(result)
                await self.send_log(
                    "Say Command",
                    f"{ctx.author.mention} used `say`, sent: `{message}`",
                    discord.Color.teal(),
                )
        except Exception as e:
            await ctx.send(f"Error broadcasting message: {e}")

    @minecraft.group(name="whitelist")
    async def minecraft_whitelist(self, ctx):
        """Manages the server whitelist."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @minecraft_whitelist.command(name="get")
    async def get_whitelist(self, ctx):
        """Gets all whitelisted users."""
        try:
            result = self.minecraft.whitelist_get()
            await ctx.send(result)
            await self.send_log(
                "Whitelist Get Command",
                f"{ctx.author.mention} used `whitelist get`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error getting whitelist: {e}")

    @minecraft_whitelist.command(name="add")
    async def add_user(self, ctx, username):
        """Adds a user to the whitelist."""
        try:
            result = self.minecraft.whitelist_add(username)
            await ctx.send(result)
            await self.send_log(
                "Whitelist Add Command",
                f"{ctx.author.mention} used `whitelist add` on `{username}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error adding user to whitelist: {e}")

    @minecraft_whitelist.command(name="remove")
    async def remove_user(self, ctx, username):
        """Removes a user from the whitelist."""
        try:
            result = self.minecraft.whitelist_remove(username)
            await ctx.send(result)
            await self.send_log(
                "Whitelist Remove Command",
                f"{ctx.author.mention} used `whitelist remove` on `{username}`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error removing user from whitelist: {e}")

    @minecraft_whitelist.command(name="on")
    async def enable_whitelist(self, ctx):
        """Enables the whitelist."""
        try:
            result = self.minecraft.whitelist_on()
            await ctx.send(result)
            await self.send_log(
                "Whitelist Enable Command",
                f"{ctx.author.mention} used `whitelist on`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error enabling whitelist: {e}")

    @minecraft_whitelist.command(name="off")
    async def disable_whitelist(self, ctx):
        """Disables the whitelist."""
        try:
            result = self.minecraft.whitelist_off()
            await ctx.send(result)
            await self.send_log(
                "Whitelist Disable Command",
                f"{ctx.author.mention} used `whitelist off`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error disabling whitelist: {e}")

    @minecraft_whitelist.command(name="reload")
    async def reload_whitelist(self, ctx):
        """Reloads the whitelist."""
        try:
            result = self.minecraft.whitelist_reload()
            await ctx.send(result)
            await self.send_log(
                "Whitelist Reload Command",
                f"{ctx.author.mention} used `whitelist reload`",
                discord.Color.teal(),
            )
        except Exception as e:
            await ctx.send(f"Error reloading whitelist: {e}")

    @minecraft.group(name="config")
    async def minecraft_config(self, ctx):
        """Manages the Minecraft configuration."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @minecraft_config.command(name="ip")
    async def set_ip(self, ctx, ip: str):
        """Sets the Minecraft server IP address."""
        self.bot.config["minecraft"]["ip"] = ip
        self.bot.reload_config()
        await ctx.send(f"Minecraft server IP address set to: {ip}")

    @minecraft_config.command(name="port")
    async def set_port(self, ctx, port: int):
        """Sets the Minecraft server port."""
        self.bot.config["minecraft"]["port"] = port
        self.bot.reload_config()
        await ctx.send(f"Minecraft server port set to: {port}")

    @minecraft_config.command(name="password")
    async def set_password(self, ctx, password: str):
        """Sets the Minecraft server RCON password."""
        self.bot.config["minecraft"]["password"] = password
        self.bot.reload_config()
        await ctx.send("Minecraft server RCON password updated.")

    @minecraft_config.command(name="server-id")
    async def set_server_id(self, ctx, server_id: int):
        """Sets the Discord server ID for Minecraft commands."""
        self.bot.config["minecraft"]["discord_server_id"] = server_id
        self.bot.reload_config()
        await ctx.send(f"Discord server ID for Minecraft commands set to: {server_id}")

    @minecraft_config.command(name="add-role")
    async def add_permitted_role(self, ctx, role: discord.Role):
        """Adds a permitted role for Minecraft commands."""
        self.bot.config["minecraft"]["permitted_roles"].append(role.name)
        self.bot.reload_config()
        await ctx.send(
            f"Role '{role.name}' added to permitted roles for Minecraft commands."
        )

    @minecraft_config.command(name="remove-role")
    async def remove_permitted_role(self, ctx, role: discord.Role):
        """Removes a permitted role for Minecraft commands."""
        try:
            self.bot.config["minecraft"]["permitted_roles"].remove(role.name)
            self.bot.reload_config()
            await ctx.send(
                f"Role '{role.name}' removed from permitted roles for Minecraft commands."
            )
        except ValueError:
            await ctx.send(f"Role '{role.name}' is not in the permitted roles list.")

    @minecraft_config.command(name="log-channel")
    async def set_log_channel(self, ctx, log_channel: discord.TextChannel):
        """Sets the log channel for Minecraft server events."""
        self.bot.config["minecraft"]["log_channel_id"] = log_channel.id
        self.bot.reload_config()
        await ctx.send(f"Minecraft Server Log Channel set to: {log_channel.mention}")

    @minecraft_config.command(name="invite-link")
    async def set_invite_link(self, ctx, invite: discord.Invite):
        """Sets the Discord server invite link for the Minecraft server."""
        self.bot.config["minecraft"]["log_channel_id"] = invite
        self.bot.reload_config()
        await ctx.send(f"Minecraft Server Invite Link set to: {invite}")

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload):
        user, guild_id = payload
        if guild_id != self.main_server.id:
            return
        user_id = user.id

        # Check if user was in minecraft:
        check = await self.database.get_minecraft_user(user_id)

        if not check:
            return

        self.minecraft.whitelist_remove(check)
        await self.database.remove_minecraft_user(user_id)
        await self.send_log(
            "User Removed",
            "User removed from whitelist due to leaving, being banned or kicked from Lewd Corner",
            discord.Color.red(),
        )


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
