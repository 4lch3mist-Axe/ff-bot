import datetime
import time
import discord

from ui.embed_factory import (
    sauron_embed,
    EMBED_COLOR_INFO,
    EMBED_COLOR_MAIN
)

from polls.manager import compute_results
from polls.storage import load_poll, save_poll
from polls.scheduler import (
    auto_close_poll,
    auto_update_poll_timer,
    alert_unvoted_members,
    safe_create_task
)
import config


COLOR_OPEN = 0x3498db    # bleu
COLOR_CLOSED = 0x95a5a6  # gris

# =========================
# VISUAL HELPERS
# =========================
def vote_bar(count: int, max_count: int, size: int = 10) -> str:
    if max_count <= 0:
        return "░" * size
    filled = int((count / max_count) * size)
    return "█" * filled + "░" * (size - filled)


# =========================
# EMBED BUILDER
# =========================
def build_poll_embed(poll: dict) -> discord.Embed:
    results = compute_results(poll)
    max_votes = max(results.values()) if results else 0

    lines = []
    for opt in poll["options"]:
        count = results.get(opt, 0)
        bar = vote_bar(count, max_votes)
        lines.append(f"**{opt}** — `{count}` vote(s)\n{bar}")

    color = EMBED_COLOR_INFO if poll["status"] == "open" else EMBED_COLOR_MAIN

    multi_state = "Activé" if poll.get("multiple", False) else "Désactivé"

    description = (
        f"**{poll['question']}**\n"
        f"🔁 *Multi-vote : {multi_state}*\n\n"
        + "\n\n".join(lines)
    )

    embed = sauron_embed(
        title="📊 Sondage",
        description=description,
        color=color
    )

    # ➕ ID du sondage visible
    embed.set_footer(
        text=f"Sauron • Observation active | ID : {poll['poll_id']}"
    )

    # =========================
    # DEADLINE DISPLAY
    # =========================
    if poll.get("ends_at"):
        ends_at = datetime.datetime.fromisoformat(poll["ends_at"])
        remaining = ends_at - datetime.datetime.utcnow()
        seconds = int(remaining.total_seconds())

        if seconds <= 0:
            deadline = "Terminé"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if days > 0:
                deadline = f"{days} jour(s) {hours}h restantes"
            else:
                deadline = f"{hours}h restantes"
    else:
        deadline = "Aucune"

    embed.add_field(name="⏱️ Deadline", value=deadline, inline=True)
    embed.add_field(
        name="📌 Statut",
        value="Ouvert" if poll["status"] == "open" else "Fermé",
        inline=True
    )
    embed.add_field(
        name="👥 Participation",
        value=f"{len(poll['votes'])} votant(s)",
        inline=False
    )
    embed.set_footer(text=f"ID du sondage : {poll['poll_id']}")
    return embed


# =========================
# BUTTONS
# =========================
class PollButton(discord.ui.Button):
    def __init__(self, poll_id: str, option: str):
        super().__init__(label=option, style=discord.ButtonStyle.primary, custom_id=f"poll_vote:{poll_id}:{option}")
        self.poll_id = poll_id
        self.option = option

    async def callback(self, interaction: discord.Interaction):
        from polls.manager import register_vote

        poll, status, action = register_vote(
            self.poll_id, interaction.user.id, self.option
        )

        if status != "ok":
            return await interaction.response.send_message(
                "🔒 Ce sondage est fermé", ephemeral=True
            )

       
        await interaction.response.send_message(
            "🗑️ Vote supprimé" if action == "removed"
            else f"✅ Vote enregistré : **{self.option}**",
            ephemeral=True
        )

        poll = load_poll(self.poll_id)
        await interaction.message.edit(
            embed=build_poll_embed(poll),
            view=PollView(poll)
        )


class PollTimerButton(discord.ui.Button):
    def __init__(self, poll: dict):
        super().__init__(
            label="⏱️ Modifier la durée" if poll.get("ends_at")
            else "⏱️ Définir une durée",
            style=discord.ButtonStyle.secondary,
            custom_id=f"poll_timer:{poll['poll_id']}"
)
        self.poll_id = poll["poll_id"]

    async def callback(self, interaction: discord.Interaction):
        poll = load_poll(self.poll_id)
        if not poll or interaction.user.id != poll["created_by"]:
            return await interaction.response.send_message(
                "❌ Réservé au créateur", ephemeral=True
            )

        await interaction.response.send_modal(
            PollDurationModal(self.poll_id)
        )


class PollNotifyAbsentsButton(discord.ui.Button):
    def __init__(self, poll: dict):
        super().__init__(
            label="📣 Notifier les absents",
            style=discord.ButtonStyle.danger,
            custom_id=f"poll_notify_absents:{poll['poll_id']}"
        )
        self.poll_id = poll["poll_id"]

    async def callback(self, interaction: discord.Interaction):
        poll = load_poll(self.poll_id)
        if not poll or poll["status"] != "open":
            return await interaction.response.send_message(
                "❌ Sondage fermé ou introuvable.",
                ephemeral=True
            )

        member = interaction.guild.get_member(interaction.user.id)
        is_admin = any(
            r.id in config.ADMIN_ROLE_IDS for r in member.roles
        )

        if interaction.user.id != poll["created_by"] and not is_admin:
            return await interaction.response.send_message(
                "❌ Action réservée au créateur ou aux admins.",
                ephemeral=True
            )

        now = int(time.time())
        last = poll.get("last_notify_ts", 0)
        cooldown = getattr(config, "POLL_NOTIFY_COOLDOWN_SECONDS", 600)

        if now - last < cooldown:
            remaining = cooldown - (now - last)
            return await interaction.response.send_message(
                f"⏳ Cooldown actif ({remaining}s restantes).",
                ephemeral=True
            )

        voters = set(poll["votes"].keys())
        targets = [
            m for m in interaction.guild.members
            if any(r.id in poll.get("notify_roles", []) for r in m.roles)
            and str(m.id) not in voters
            and not m.bot
        ]

        if not targets:
            return await interaction.response.send_message(
                "✅ Tout le monde a voté.",
                ephemeral=True
            )

        mentions = " ".join(m.mention for m in targets)

        await interaction.channel.send(
            f"📣 **Rappel sondage** — merci de voter :\n{mentions}"
        )

        poll["last_notify_ts"] = now
        save_poll(poll)

        await interaction.response.send_message(
            "📨 Absents notifiés.",
            ephemeral=True
        )
class PollMultiVoteButton(discord.ui.Button):
    def __init__(self, poll: dict):
        label = "🔁 Multi-vote : ON" if poll.get("multiple", False) else "🔁 Multi-vote : OFF"
        style = discord.ButtonStyle.success if poll.get("multiple", False) else discord.ButtonStyle.secondary

        super().__init__(
            label=label,
            style=style,
            custom_id=f"poll_multivote:{poll['poll_id']}"
        )

        self.poll_id = poll["poll_id"]

    async def callback(self, interaction: discord.Interaction):
        poll = load_poll(self.poll_id)
        if not poll or poll["status"] != "open":
            return await interaction.response.send_message(
                "❌ Sondage fermé",
                ephemeral=True
            )

        if interaction.user.id != poll["created_by"]:
            return await interaction.response.send_message(
                "❌ Réservé au créateur",
                ephemeral=True
            )

        poll["multiple"] = not poll.get("multiple", False)
        save_poll(poll)

        await interaction.message.edit(
            embed=build_poll_embed(poll),
            view=PollView(poll)
        )

        await interaction.response.send_message(
            f"🔁 Multi-vote {'activé' if poll['multiple'] else 'désactivé'}",
            ephemeral=True
        )

# =========================
# MODAL
# =========================
class PollDurationModal(discord.ui.Modal, title="⏱️ Durée du sondage (jours)"):
    days = discord.ui.TextInput(
        label="Nombre de jours", placeholder="Ex: 3", required=True
    )

    def __init__(self, poll_id: str):
        super().__init__()
        self.poll_id = poll_id

    async def on_submit(self, interaction: discord.Interaction):
        poll = load_poll(self.poll_id)
        if not poll or poll["status"] != "open":
            return await interaction.response.send_message(
                "❌ Sondage fermé", ephemeral=True
            )

        days = int(self.days.value)
        minutes = days * 1440
        poll["duration_minutes"] = minutes
        poll["ends_at"] = (
            datetime.datetime.utcnow()
            + datetime.timedelta(minutes=minutes)
        ).isoformat()
        poll["alert_sent"] = False
        save_poll(poll)

        client = interaction.client
        pid = poll["poll_id"]

        safe_create_task(auto_close_poll(client, pid), f"auto_close:{pid}")
        safe_create_task(alert_unvoted_members(client, pid), f"alert:{pid}")
        safe_create_task(
            auto_update_poll_timer(client, pid, 1),
            f"refresh:{pid}"
        )

        await interaction.response.send_message(
            f"⏱️ Durée mise à jour : **{days} jour(s)**",
            ephemeral=True
        )

        await interaction.message.edit(
            embed=build_poll_embed(poll),
            view=PollView(poll)
        )


# =========================
# VIEW
# =========================
class PollView(discord.ui.View):
    def __init__(self, poll: dict):
        super().__init__(timeout=None)

        for opt in poll["options"]:
            self.add_item(PollButton(poll["poll_id"], opt))

        if poll["status"] == "open":
            self.add_item(PollTimerButton(poll))
            self.add_item(PollMultiVoteButton(poll))
            self.add_item(PollNotifyAbsentsButton(poll))
