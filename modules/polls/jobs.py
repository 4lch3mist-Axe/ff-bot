from core.logger import module_log
from modules.polls.resume import resume_poll_views
from modules.polls.scheduler import resume_open_polls


async def setup(bot):
    module_log("polls", "starting jobs")

    await resume_poll_views(bot)
    await resume_open_polls(bot)

    module_log("polls", "jobs started")
