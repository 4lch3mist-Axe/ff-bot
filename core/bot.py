import discord
from discord import app_commands

from core.logger import log
from core.module_loader import load_modules, load_module_jobs


class PollBot(discord.Client):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)

        self.guild_id = guild_id
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        load_modules(self.tree, self.guild_id)

        guild = discord.Object(id=self.guild_id)
        await self.tree.sync(guild=guild)

        await load_module_jobs(self)

        log("Slash commands synced", "READY")

