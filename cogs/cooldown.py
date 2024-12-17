import os
import sqlite3
import discord
from discord.ext import commands, tasks
import datetime
import json
from .utils import checks


class cooldown(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permitted_roles = bot.config.get("permitted_roles")
        self.cooldown_channels = bot.config.get("cooldown_channels")  # Return a dict.
        self.log_channel_id = bot.config.get("log_channel_id")
        self.log_channel = self.bot.get_channel(self.log_channel_id)
        self.db_path = "cooldown_database.db"  # Path to your database file
        self.level_roles = self.get_level_roles()

    def get_level_roles(self):
        """
        Gets all roles that follow the format '[Level N] Name'
        and stores them in self.level_roles.
        """
        level_roles = {}
        for role in self.bot.guilds[0].roles:
            try:
                if not role.name.startswith("[Level "):
                    continue  # Skip roles that don't match the format

                level_str = role.name.split("]")[0]  # Get the part before the ']'
                level_number = int(level_str.split("[Level ")[1])  # Extract the number
                level_roles[level_number] = role.id
            except (IndexError, ValueError):
                pass  # Ignore roles that don't match the format
        return level_roles

    def get_user_level(self, user: discord.Member):
        """
        Calculates the user's level multiplier based on their highest level role.

        For every 20 levels, the user receives +1 to their multiplier, starting from 0.
        """
        highest_level = 0
        for role in user.roles:
            for level_number, role_id in self.level_roles.items():
                if role.id == role_id and level_number > highest_level:
                    highest_level = level_number

        return highest_level // 20

    @commands.group(invoke_without_command=True, aliases=["cd"])
    @checks.is_mod()
    @checks.in_lc()
    async def cooldown(self, ctx):
        """Shows the cooldowns."""
        # sourcery skip: move-assign-in-block, use-join
        desc = ""
        embed = discord.Embed(color=0x7ACFE4, title="Channel Cooldowns:")
        for k, v in self.bot.config["cooldown_channels"].items():
            desc += f"\n <#{k}> - `{v} minutes`"
        embed.description = desc
        embed.set_footer(
            text=f"Set cooldown with: {ctx.prefix}cooldown set <channel> <minutes>"
        )
        await ctx.send(embed=embed)

    @cooldown.command()
    async def set(self, ctx, channel: discord.TextChannel, cooldown_time: int):
        """Sets the cooldown for the specified channel."""
        try:
            # Load the config file
            with open("config.json", "r") as f:
                config = json.load(f)

            channel_id = str(channel.id)

            # Check if the channel is already in the cooldown_channels list
            if channel_id not in config["cooldown_channels"]:
                # If not, add it with the provided cooldown time
                config["cooldown_channels"][channel_id] = cooldown_time
                await ctx.send(
                    f":white_check_mark: Added {channel.mention} to the cooldown channel list with a cooldown of {cooldown_time} minutes."
                )
            else:
                # If it is, update the cooldown time
                old_cooldown = config["cooldown_channels"][channel_id]
                config["cooldown_channels"][channel_id] = cooldown_time
                await ctx.send(
                    f":white_check_mark: {channel.mention} cooldown set to **{cooldown_time}** minutes."
                )

                if self.log_channel:
                    embed = discord.Embed(
                        title="Cooldown Changed",
                        description=f"{ctx.author.mention} used the `cooldown set` on {channel.mention}. \nOld cooldown: **{old_cooldown}** minutes\nNew cooldown: **{cooldown_time}** minutes ",
                        color=discord.Color.blue(),
                    )
                    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                    await self.log_channel.send(embed=embed)

            # Save the updated config file
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)

            self.bot.reload_config()
            self.cooldown_channels = self.bot.config.get("cooldown_channels")

        except Exception as e:
            print(f"Error setting cooldown: {e}")
            await ctx.send(
                "An error occurred while setting the cooldown.\nPinging the idiot who made the bot <@289890066514575360>"
            )

    @cooldown.command()
    async def check(self, ctx, user: discord.Member = None):
        """Checks the cooldown for the selected user in all cooldown channels."""

        if not user:
            user = ctx.author

        embed = discord.Embed(
            title=f"Cooldown Status for {user.name}", color=discord.Color.blue()
        )

        for channel_id, cooldown_duration in self.cooldown_channels.items():
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                embed.add_field(
                    name=f"Channel {channel_id} (Not Found)",
                    value="Channel not found.",
                    inline=False,
                )
                continue

            # Get cooldown end time from the database
            cooldown_end_time = await self.bot.get_cog("Database").get_cooldown(
                str(user.id), channel_id
            )

            if cooldown_end_time:
                now = datetime.datetime.now(datetime.timezone.utc)
                if now < cooldown_end_time:
                    remaining_time = (cooldown_end_time - now).total_seconds() / 60
                    embed.add_field(
                        name=channel.name,
                        value=f"{user.mention} can post again {discord.utils.format_dt(cooldown_end_time, 'R')}.",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name=channel.name,
                        value=f"{user.mention} is not on cooldown.",
                        inline=False,
                    )
            else:
                embed.add_field(
                    name=channel.name,
                    value=f"{user.mention} is not on cooldown.",
                    inline=False,
                )

        await ctx.send(embed=embed)

    @cooldown.command(aliases=["clear"])
    async def reset(
        self, ctx, user: discord.Member, channel: discord.TextChannel = None
    ):
        """
        Resets the cooldown for the selected user.

        If a channel is specified, resets the cooldown only for that channel.
        Otherwise, resets all cooldowns for the user.
        """
        user_id = str(user.id)

        if channel:
            channel_id = str(channel.id)
            try:
                # Delete the cooldown entry from the database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM cooldowns
                    WHERE user_id = ? AND channel_id = ?
                """,
                    (user_id, channel_id),
                )
                conn.commit()
                conn.close()
                await ctx.send(
                    f":white_check_mark: Cooldown reset for {user.mention} in {channel.mention}."
                )

                # Log the reset action
                if self.log_channel:
                    embed = discord.Embed(
                        title="Cooldown Reset Command Used",
                        description=f"{ctx.author.mention} used the `cooldown reset` on {user.mention} in {channel.mention}.",
                        color=discord.Color.blue(),
                    )
                    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                    await self.log_channel.send(embed=embed)
            except Exception as e:
                print(f"Error resetting cooldown in database: {e}")
                await ctx.send(
                    f"An error occurred while resetting the cooldown for {user.mention} in {channel.mention}."
                )
        else:
            try:
                # Delete all cooldown entries for the user from the database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM cooldowns
                    WHERE user_id = ?
                """,
                    (user_id,),
                )
                conn.commit()
                conn.close()
                await ctx.send(
                    f":white_check_mark: All cooldowns reset for {user.mention}."
                )

                # Log the reset action
                if self.log_channel:
                    embed = discord.Embed(
                        title="Cooldown Reset Command Used",
                        description=f"{ctx.author.mention} used the `cooldown reset` on {user.mention} in all channels.",
                        color=discord.Color.blue(),
                    )
                    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                    await self.log_channel.send(embed=embed)
            except Exception as e:
                print(f"Error resetting cooldowns in database: {e}")
                await ctx.send(
                    f"An error occurred while resetting all cooldowns for {user.mention}."
                )

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handles the cooldown logic when a message is sent."""
        if (
            message.author == self.bot.user
            or message.webhook_id
            or message.author.id == 470723870270160917
        ):
            return

        channel_id = str(message.channel.id)
        if channel_id in self.cooldown_channels:
            now = datetime.datetime.now(datetime.timezone.utc)  # Define 'now' here
            has_permitted_role = any(
                role.name in self.permitted_roles
                or str(role.id) in self.permitted_roles
                for role in message.author.roles
            )
            if has_permitted_role:
                return  # Allow the message if the user has a permitted role

            user_id = str(message.author.id)

            # Check cooldown for the specific channel where the message was sent
            cooldown_duration = self.cooldown_channels[channel_id]

            # Calculate cooldown reduction based on user level
            reduce_by = self.bot.config.get(
                "cooldown_reduce_by", 0
            ) * self.get_user_level(message.author)
            cooldown_duration -= reduce_by  # Reduce cooldown duration
            # Get cooldown end time from the database for the specific channel
            cooldown_end_time = await self.bot.get_cog("Database").get_cooldown(
                user_id, channel_id
            )

            if cooldown_end_time is None or message.created_at > cooldown_end_time:
                # No active cooldown or cooldown has expired, set a new cooldown for all channels
                for channel_id, duration in self.cooldown_channels.items():
                    new_cooldown_end_time = now + datetime.timedelta(
                        minutes=duration - reduce_by
                    )
                    await self.bot.get_cog("Database").insert_cooldown(
                        user_id, channel_id, new_cooldown_end_time
                    )
            else:
                # Cooldown is active, handle violation

                # Update cooldown end time for all channels in the database

                remaining_time = (
                    cooldown_end_time - message.created_at
                ).total_seconds() / 60

                # Create cooldown information for all channels
                cooldown_info = []
                for channel_id, duration in self.cooldown_channels.items():
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        cooldown_end_time_channel = await self.bot.get_cog(
                            "Database"
                        ).get_cooldown(user_id, channel_id)
                        if cooldown_end_time_channel:
                            remaining_time_channel = (
                                cooldown_end_time_channel - message.created_at
                            ).total_seconds() / 60
                            cooldown_expiry_channel = (
                                message.created_at
                                + datetime.timedelta(minutes=remaining_time_channel)
                            )
                            if remaining_time_channel > 0:
                                cooldown_info.append(
                                    f"{channel.mention}: {discord.utils.format_dt(cooldown_expiry_channel, 'R')}"
                                )
                            else:
                                cooldown_info.append(f"{channel.mention}: No cooldown.")

                # Create the embed with cooldown information for all channels
                embed = discord.Embed(
                    title="Lewd Corder LFP Cooldown",
                    description=f"Do not try posting your Advertisement in all channels, choose one that fits your advertisement the most. Check <#920837349833855006> Rule 1 for more info.\n\n"
                    f"You can post again in:\n" + "\n".join(cooldown_info),
                    color=discord.Color.orange(),
                )
                embed.set_footer(text="Kind regards, LC Staff Team.")

                try:
                    await message.author.send(embed=embed)
                    if self.log_channel:
                        embed = discord.Embed(
                            title="Cooldown Violation",
                            description=f"{message.author.mention} tried to send a message in {message.channel.mention} but is on cooldown:\n\n"
                            + "\n".join(cooldown_info),
                            color=discord.Color.red(),
                        )
                        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                        embed.set_footer(text=f"{message.author.id}")
                        await self.log_channel.send(embed=embed)

                except discord.HTTPException:
                    if self.log_channel:
                        embed = discord.Embed(
                            title="Cooldown Violation | FAILED TO DM",
                            description=f"{message.author.mention} tried to send a message in {message.channel.mention} but is on cooldown:\n\n"
                            + "\n".join(cooldown_info),
                            color=discord.Color.red(),
                        )
                        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
                        embed.set_footer(text=f"{message.author.id}")
                        await self.log_channel.send(embed=embed)
                    print(f"Failed to DM {message.author}")

                await message.delete()

    @cooldown.command()
    async def config(self, ctx):
        """Shows the current cooldown configuration."""
        try:
            with open("config.json", "r") as f:
                config = json.load(f)

            cooldown_channels = config.get("cooldown_channels", {})
            permitted_roles_list = config.get("permitted_roles", [])

            embed = discord.Embed(
                title="Cooldown Configuration", color=discord.Color.blue()
            )

            if cooldown_channels:
                channel_mentions = []
                for channel_id, cooldown_duration in cooldown_channels.items():
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        channel_mentions.append(
                            f"{channel.mention}: {cooldown_duration} minutes"
                        )
                    else:
                        channel_mentions.append(
                            f"`{channel_id}` (Channel not found): {cooldown_duration} minutes"
                        )
                embed.add_field(
                    name="Cooldown Channels",
                    value="\n".join(channel_mentions),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Cooldown Channels",
                    value="No channels configured",
                    inline=False,
                )

            if permitted_roles_list:
                roles_str = ", ".join([f"`{role}`" for role in permitted_roles_list])
                embed.add_field(name="Permitted Roles", value=roles_str, inline=False)
            else:
                embed.add_field(
                    name="Permitted Roles", value="No roles configured", inline=False
                )

            await ctx.send(embed=embed)

        except (Exception, Exception) as e:
            print(f"Error showing cooldown configuration: {e}")
            await ctx.send(
                "An error occurred while showing the cooldown configuration."
            )

    @commands.command(hidden=True)
    @checks.is_mod()
    @checks.in_lc()
    async def debug_user(self, ctx, user: discord.Member):
        """Debugs cooldown status for a user in all cooldown channels."""
        user_id = str(user.id)
        embed = discord.Embed(title=f"Debug: {user.name}", color=discord.Color.blue())
        embed.add_field(name="User ID", value=user_id)

        for channel_id, cooldown_duration in self.cooldown_channels.items():
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                embed.add_field(
                    name=f"Channel {channel_id} (Not Found)",
                    value="Channel not found.",
                    inline=False,
                )
                continue

            last_message_time = await self.check_cache(user, channel_id)

            if last_message_time is None:
                last_message = await self.get_last_message_in_channel(user, 0, channel)
                if last_message:
                    last_message_time = last_message.created_at
                    # Update the cache with the fetched last_message_time
                    if user_id not in self.cooldown_cache:
                        self.cooldown_cache[user_id] = {}
                    self.cooldown_cache[user_id][channel_id] = last_message_time
                else:
                    embed.add_field(
                        name=channel.name,
                        value=f"No messages found from {user.mention} in this channel.",
                        inline=False,
                    )
                    continue

            now = datetime.datetime.now(datetime.timezone.utc)
            time_diff = (now - last_message_time).total_seconds() / 60
            remaining_time = max(0, cooldown_duration - time_diff)

            embed.add_field(
                name=f"Channel: {channel.name}",
                value=f"Last Message: {discord.utils.format_dt(last_message_time, 'F')}\n"
                f"Time Since Last Message: {time_diff:.2f} minutes\n"
                f"Remaining Cooldown: {remaining_time:.2f} minutes",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command()
    @checks.is_admin()
    @checks.in_lc()
    async def add_cooldown_channel(
        self, ctx, channel: discord.TextChannel, cooldown_time: int
    ):
        """Adds a channel to the list of cooldown channels with the specified cooldown time in minutes."""
        try:
            # Load the config file
            with open("config.json", "r") as f:
                config = json.load(f)

            # Add the channel ID and cooldown time to the cooldown_channels dictionary
            channel_id = str(
                channel.id
            )  # Convert to string for consistency with config file
            if channel_id not in config["cooldown_channels"]:
                config["cooldown_channels"][channel_id] = cooldown_time

                # Save the updated config file
                with open("config.json", "w") as f:
                    json.dump(config, f, indent=4)

                # Update the cooldown_channels variable
                self.bot.reload_config()
                self.cooldown_channels = self.bot.config["cooldown_channels"]

                await ctx.send(
                    f":white_check_mark: Added {channel.mention} to the cooldown channel list with a cooldown of {cooldown_time} minutes."
                )
            else:
                await ctx.send(
                    f"{channel.mention} is already in the cooldown channel list."
                )

        except Exception as e:
            print(f"Error adding cooldown channel: {e}")
            await ctx.send(
                "An error occurred while adding the cooldown channel.\nPinging the idiot who made the bot <@289890066514575360>"
            )

    @commands.command()
    @checks.is_admin()
    @checks.in_lc()
    async def remove_cooldown_channel(self, ctx, channel: discord.TextChannel):
        """Removes a channel from the list of cooldown channels."""
        try:
            # Load the config file
            with open("config.json", "r") as f:
                config = json.load(f)

            # Remove the channel ID from the cooldown_channels dictionary
            channel_id = str(
                channel.id
            )  # Convert to string for consistency with config file
            if channel_id in config["cooldown_channels"]:
                del config["cooldown_channels"][channel_id]

                # Save the updated config file
                with open("config.json", "w") as f:
                    json.dump(config, f, indent=4)

                # Update the cooldown_channels variable
                self.bot.reload_config()
                self.cooldown_channels = self.bot.config["cooldown_channels"]

                await ctx.send(
                    f":white_check_mark: Removed {channel.mention} from the cooldown channel list."
                )
            else:
                await ctx.send(
                    f"{channel.mention} is not in the cooldown channel list."
                )

        except Exception as e:
            print(f"Error removing cooldown channel: {e}")
            await ctx.send(
                "An error occurred while removing the cooldown channel.\nPinging the idiot who made the bot <@289890066514575360>"
            )

    @commands.command()
    @checks.is_mod()
    @checks.in_lc()
    async def show_cooldown_channels(self, ctx):
        """Shows all channels where the cooldown is active, including their cooldown durations."""
        try:
            with open("config.json", "r") as f:
                config = json.load(f)

            cooldown_channels = config.get("cooldown_channels", {})
            if cooldown_channels:
                # Convert channel IDs to channel mentions with cooldown durations
                channel_mentions = []
                for channel_id, cooldown_duration in cooldown_channels.items():
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        channel_mentions.append(
                            f"{channel.mention} ({cooldown_duration} minutes)"
                        )
                    else:
                        channel_mentions.append(
                            f"`{channel_id}` (Channel not found) ({cooldown_duration} minutes)"
                        )

                channels_str = "\n".join(channel_mentions)
                await ctx.send(f"Cooldown channels:\n{channels_str}")
            else:
                await ctx.send("There are no cooldown channels configured.")

        except Exception as e:
            print(f"Error showing cooldown channels: {e}")
            await ctx.send("An error occurred while showing the cooldown channels.")

    @commands.command()
    @checks.is_admin()
    @checks.in_lc()
    async def add_permitted_role(self, ctx, *, role: discord.Role):
        """Adds a role to the list of permitted roles."""
        try:
            with open("config.json", "r") as f:
                config = json.load(f)

            if (
                role.name not in config["permitted_roles"]
                and str(role.id) not in config["permitted_roles"]
            ):
                config["permitted_roles"].append(role.name)  # Add the role name

                with open("config.json", "w") as f:
                    json.dump(config, f, indent=4)

                self.bot.reload_config()
                self.permitted_roles = self.bot.config["permitted_roles"]
                await ctx.send(
                    f":white_check_mark: Added the role `{role.name}` to the permitted roles list."
                )
            else:
                await ctx.send(
                    f"The role `{role.name}` is already in the permitted roles list."
                )

        except Exception as e:
            print(f"Error adding permitted role: {e}")
            await ctx.send("An error occurred while adding the permitted role.")

    @commands.command()
    @checks.is_admin()
    @checks.in_lc()
    async def remove_permitted_role(self, ctx, *, role: discord.Role):
        """Removes a role from the list of permitted roles."""
        try:
            with open("config.json", "r") as f:
                config = json.load(f)

            if (
                role.name in config["permitted_roles"]
                or str(role.id) in config["permitted_roles"]
            ):
                # Try removing by name first, then by ID if not found
                try:
                    config["permitted_roles"].remove(role.name)
                except ValueError:
                    config["permitted_roles"].remove(str(role.id))

                with open("config.json", "w") as f:
                    json.dump(config, f, indent=4)

                self.bot.reload_config()
                permitted_roles = self.bot.config["permitted_roles"]
                await ctx.send(
                    f":white_check_mark: Removed the role `{role.name}` from the permitted roles list."
                )
            else:
                await ctx.send(
                    f"The role `{role.name}` is not in the permitted roles list."
                )

        except Exception as e:
            print(f"Error removing permitted role: {e}")
            await ctx.send("An error occurred while removing the permitted role.")

    @commands.command()
    @checks.is_mod()
    @checks.in_lc()
    async def show_permitted_roles(self, ctx):
        """Shows all permitted roles."""
        try:

            permitted_roles_list = self.bot.config.get(
                "permitted_roles", []
            )  # Rename to avoid shadowing
            if permitted_roles_list:
                roles_str = ", ".join([f"`{role}`" for role in permitted_roles_list])
                await ctx.send(f"Permitted roles: {roles_str}")
            else:
                await ctx.send("There are no permitted roles.")

        except Exception as e:
            print(f"Error showing permitted roles: {e}")
            await ctx.send("An error occurred while showing the permitted roles.")


# In your main bot file:
# Load the cog:
async def setup(bot):
    await bot.add_cog(cooldown(bot))
