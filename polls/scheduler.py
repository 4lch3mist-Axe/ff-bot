import asyncio
import datetime
import discord

from core.logger import log
from polls.storage import load_poll, save_poll
import config



# =========================
# SAFE TASK WRAPPER
# =========================
def safe_create_task(coro, name: str):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log(f"POLL task skipped (no loop): {name}", "ERROR")
        return

    async def wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            log(f"POLL task cancelled: {name}", "POLL")
        except Exception as e:
            log(f"POLL task crash [{name}]: {e}", "ERROR")

    loop.create_task(wrapper())


# =========================
# CORE CLOSE
# =========================
async def close_poll_and_process(
    client: discord.Client,
    poll_id: str,
    reason: str = "auto"
):
    poll = load_poll(poll_id)
    if not poll or poll["status"] != "open":
        return

    poll["status"] = "closed"
    save_poll(poll)

    await notify_missing_voters_on_close(client, poll_id, reason)

    log(f"POLL closed id={poll_id} reason={reason}", "POLL")


# =========================
# AUTO CLOSE
# =========================
async def auto_close_poll(client: discord.Client, poll_id: str):
    poll = load_poll(poll_id)
    if not poll or not poll.get("ends_at"):
        return

    ends_at = datetime.datetime.fromisoformat(poll["ends_at"])
    delay = (ends_at - datetime.datetime.utcnow()).total_seconds()

    if delay > 0:
        await asyncio.sleep(delay)

    poll = load_poll(poll_id)
    if not poll or poll["status"] != "open":
        return

    await close_poll_and_process(client, poll_id, "auto")

    poll = load_poll(poll_id)
    if not poll:
        return

    try:
        from polls.ui import build_poll_embed

        channel = client.get_channel(poll["channel_id"])
        if not channel:
            return

        message = await channel.fetch_message(poll["message_id"])
        await message.edit(
            embed=build_poll_embed(poll),
            view=None
        )
    except Exception as e:
        log(f"POLL close edit failed: {e}", "ERROR")


# =========================
# TIMER REFRESH
# =========================
async def auto_update_poll_timer(
    client: discord.Client,
    poll_id: str,
    refresh_minutes: int
):
    refresh_seconds = refresh_minutes * 60

    while True:
        poll = load_poll(poll_id)
        if (
            not poll
            or poll["status"] != "open"
            or not poll.get("ends_at")
        ):
            return

        ends_at = datetime.datetime.fromisoformat(poll["ends_at"])
        remaining = (ends_at - datetime.datetime.utcnow()).total_seconds()

        if remaining <= refresh_seconds:
            return

        try:
            from polls.ui import build_poll_embed, PollView

            channel = client.get_channel(poll["channel_id"])
            if not channel:
                return

            message = await channel.fetch_message(poll["message_id"])
            await message.edit(
                embed=build_poll_embed(poll),
                view=PollView(poll)
            )

            log(
                f"POLL timer refresh id={poll_id} "
                f"remaining={int(remaining // 60)}min",
                "POLL"
            )
        except Exception as e:
            log(f"POLL timer refresh failed: {e}", "ERROR")

        await asyncio.sleep(refresh_seconds)


# =========================
# MISSING VOTERS ON CLOSE
# =========================
async def notify_missing_voters_on_close(
    client: discord.Client,
    poll_id: str,
    reason: str
):
    poll = load_poll(poll_id)
    if not poll or not poll.get("notify_roles"):
        return

    guild = client.get_guild(poll["guild_id"])
    if not guild:
        return

    voters = set(poll["votes"].keys())

    missing = [
        m for m in guild.members
        if any(r.id in poll["notify_roles"] for r in m.roles)
        and str(m.id) not in voters
        and not m.bot
    ]

    from polls.non_voters import register_missed_vote
    for m in missing:
        register_missed_vote(m, guild)

    if not missing:
        return

    channel_id = config.POLL_MISSING_VOTES_CHANNEL_ID
    if not channel_id:
        return

    channel = client.get_channel(channel_id)
    if not channel:
        return

    try:
        mentions = " ".join(m.mention for m in missing)

        await channel.send(
            f"🛑 **Sondage terminé — votes manquants**\n"
            f"**{poll['question']}**\n\n"
            f"👤 **Absents :**\n{mentions}"
        )
    except Exception as e:
        log(f"POLL missing voters send failed: {e}", "ERROR")

# =========================
# ALERT 25%
# =========================
async def alert_unvoted_members(
    client: discord.Client,
    poll_id: str
):
    poll = load_poll(poll_id)
    if not poll or poll["alert_sent"]:
        return

    if not poll.get("ends_at") or not poll.get("notify_roles"):
        return

    created_at = datetime.datetime.fromisoformat(poll["created_at"])
    ends_at = datetime.datetime.fromisoformat(poll["ends_at"])

    total = (ends_at - created_at).total_seconds()
    alert_at = ends_at - datetime.timedelta(seconds=total * 0.25)

    delay = (alert_at - datetime.datetime.utcnow()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)

    poll = load_poll(poll_id)
    if not poll or poll["status"] != "open" or poll["alert_sent"]:
        return

    guild = client.get_guild(poll["guild_id"])
    if not guild:
        return

    voters = set(poll["votes"].keys())

    targets = [
        m for m in guild.members
        if any(r.id in poll["notify_roles"] for r in m.roles)
        and str(m.id) not in voters
        and not m.bot
    ]

    if not targets:
        return

    try:
        channel = client.get_channel(poll["channel_id"])
        mentions = " ".join(m.mention for m in targets)

        await channel.send(
            f"⏰ **Rappel sondage** — il reste peu de temps pour voter !\n{mentions}"
        )

        for m in targets:
            try:
                await m.send(
                    f"⏰ **Rappel sondage**\n"
                    f"Il reste peu de temps pour voter sur :\n"
                    f"**{poll['question']}**"
                )
            except Exception:
                pass
    except Exception as e:
        log(f"POLL alert failed: {e}", "ERROR")

    poll["alert_sent"] = True
    save_poll(poll)

from polls.polls_db import fetch_open_polls_with_deadline
from polls.scheduler import (
    auto_close_poll,
    alert_unvoted_members,
    auto_update_poll_timer,
)



async def resume_open_polls(client):
    polls = fetch_open_polls_with_deadline()

    for poll in polls:
        pid = poll["poll_id"]

        safe_create_task(
            auto_close_poll(client, pid),
            f"auto_close:{pid}"
        )

        safe_create_task(
            alert_unvoted_members(client, pid),
            f"alert:{pid}"
        )

        safe_create_task(
            auto_update_poll_timer(client, pid, 1),
            f"refresh:{pid}"
        )
