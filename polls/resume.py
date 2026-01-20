import os
from polls.storage import ACTIVE_DIR, load_poll
from polls.ui import PollView
from core.logger import log


async def resume_poll_views(bot):
    if not os.path.exists(ACTIVE_DIR):
        log("POLL resume views: no active dir", "POLL")
        return

    restored = 0

    for file in os.listdir(ACTIVE_DIR):
        if not file.endswith(".json"):
            continue

        poll_id = file.replace("poll_", "").replace(".json", "")
        poll = load_poll(poll_id)

        if not poll or poll.get("status") != "open":
            continue

        bot.add_view(PollView(poll))
        restored += 1

    log(f"POLL resume views: {restored} poll(s) restored", "POLL")
