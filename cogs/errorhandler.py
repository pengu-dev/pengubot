import discord
from discord.ext import commands
import traceback


class ErrorHandler(commands.Cog):
    """
    A comprehensive cog for handling errors globally in the bot.
    """

    def __init__(self, bot):
        self.bot = bot
        self.debug_user_id = 289890066514575360  # User ID for receiving full tracebacks
        self.bot.send_log_to_donald = self.send_to_donald

    async def send_to_donald(self, message):
        try:
            debug_user = await self.bot.fetch_user(self.debug_user_id)

            await debug_user.send(f"An error occurred in command `\n{message}")
        except Exception as e:
            print(f"Failed to DM debug user: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """
        Handles errors that occur during command invocation.
        """

        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.MissingRequiredArgument):
            cmd = ctx.command
            syntax = f"{ctx.prefix}{cmd.qualified_name} "
            for param in cmd.clean_params.values():
                if param.default is param.empty:
                    syntax += f"<{param.name}> "
                else:
                    syntax += f"[{param.name}] "

            embed = discord.Embed(
                title="Missing Argument",
                description=f"You are missing a required argument: **{error.param}**\n"
                f"Correct syntax: `{syntax.strip()}`",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="Cooldown",
                description=f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                color=discord.Color.blue(),
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="Bad Argument",
                description=f"You provided an invalid argument: {error}",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="Check Failure",
                description=error.args[0],
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)

        elif isinstance(error, commands.RoleNotFound):
            embed = discord.Embed(
                title="Role Not Found",
                description=f"Could not find {error.argument} role. Try using the role ID.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)

        else:
            print(f"Ignoring exception in command {ctx.command}:", error)
            embed = discord.Embed(
                title="Unexpected Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red(),
            )
            embed.set_footer(
                text="I've already informed the stupid penguin who wrote this bot"
            )
            await ctx.send(embed=embed)

            # DM the full traceback to the debug user
            try:
                debug_user = await self.bot.fetch_user(self.debug_user_id)
                error_message = f"```python\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}\n```"
                print(error_message)

                # Write error to file
                with open("error.txt", "w") as f:
                    f.write(
                        f"An error occurred in command `{ctx.command}`:\n{error_message}"
                    )

                # Send the file
                await debug_user.send(file=discord.File("error.txt"))

            except Exception as e:
                await ctx.send(
                    "Couldn't DM The Penguin, pinging him instead <@289890066514575360>"
                )
                print(f"Failed to send error message: {e}")


# In your main bot file:
async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
