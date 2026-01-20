import discord
from discord import app_commands

from core.logger import log

from modules.polls.commands import setup_poll_commands
from modules.polls.resume import resume_poll_views
from modules.polls.scheduler import resume_open_polls


class PollBot(discord.Client):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)

        self.guild_id = guild_id
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        setup_poll_commands(self.tree, self.guild_id)

        guild = discord.Object(id=self.guild_id)
        await self.tree.sync(guild=guild)

        log("Slash commands synced", "READY")

    async def on_ready(self):
        log(f"PollBot connecté en tant que {self.user}", "READY")
        await resume_poll_views(self)
        await resume_open_polls(self)
