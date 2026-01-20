# main.py
import discord
from discord import app_commands

from config import DISCORD_TOKEN, GUILD_ID
from core.logger import log

from polls.commands import setup_poll_commands
from polls.resume import resume_poll_views
from polls.scheduler import resume_open_polls
from polls.polls_db import init_db


class PollBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        setup_poll_commands(self.tree, GUILD_ID)
        guild = discord.Object(id=GUILD_ID)
        await self.tree.sync(guild=guild)
        log("Slash commands synced", "READY")

    async def on_ready(self):
        log(f"PollBot connecté en tant que {self.user}", "READY")
        await resume_poll_views(self)
        await resume_open_polls(self)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("POLLBOT_TOKEN manquant")

    init_db()

    bot = PollBot()
    bot.run(DISCORD_TOKEN)
