import discord
from discord.ext import commands
import aiohttp
from .utils import checks


class penguin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @checks.is_donald()
    async def penguin(self, ctx):
        API_URL = "https://penguin.sjsharivker.workers.dev/api"

        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as resp:
                data = await resp.json()
                gif_url = data["img"]

        embed = discord.Embed(color=discord.Color.random())
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(penguin(bot))
