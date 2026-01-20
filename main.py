# main.py
from config import DISCORD_TOKEN, GUILD_ID
from core.bot import PollBot
from modules.polls.polls_db import init_db


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("POLLBOT_TOKEN manquant")

    init_db()

    bot = PollBot(guild_id=GUILD_ID)
    bot.run(DISCORD_TOKEN)
