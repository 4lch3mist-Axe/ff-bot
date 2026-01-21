import discord
from discord import app_commands

import config

from core.logger import log
from core.logger import module_log

from modules.polls.manager import (
    create_poll,
    generate_poll_id
)
from modules.polls.ui import (
    build_poll_embed,
    PollView
)
from modules.polls.scheduler import (
    safe_create_task,
    auto_close_poll,
    auto_update_poll_timer,
    alert_unvoted_members
)
from modules.polls.non_voters import (load_non_voters, reset_user_absences, reset_all_absences)

from modules.polls.polls_db import get_poll, get_votes
from modules.polls.utils import paginate

class PollStatusView(discord.ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=180)
        self.embeds = embeds
        self.index = 0

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=self.embeds[self.index],
            view=self
        )

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _):
        if self.index > 0:
            self.index -= 1
        await self.update(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _):
        if self.index < len(self.embeds) - 1:
            self.index += 1
        await self.update(interaction)

    @discord.ui.button(label="❌", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, _):
        await interaction.response.edit_message(
            content="❌ Consultation fermée.",
            embed=None,
            view=None
        )
# =========================
# SETUP
# =========================
def setup_poll_commands(tree: app_commands.CommandTree, GUILD_ID: int):
    # =========================
    # /poll
    # =========================
    @tree.command(name="poll", guild=discord.Object(id=GUILD_ID))
    @app_commands.describe(
        question="Question du sondage",
        options="4 Choix séparés par un ; (ex: Oui;Non;Peut-être)"
    )
    async def poll_simple(
        interaction: discord.Interaction,
        question: str,
        options: str
    ):
        member = interaction.guild.get_member(interaction.user.id)

        if not member or not any(
            role.id in config.ADMIN_ROLE_IDS
            for role in member.roles
        ):
            await interaction.response.send_message(
                "❌ Commande réservée aux administrateurs",
                ephemeral=True
            )
            return

        opts = [o.strip() for o in options.split(";") if o.strip()]
        if not 2 <= len(opts) <= 5:
            await interaction.response.send_message(
                "❌ Entre 2 et 5 choix sont requis",
                ephemeral=True
            )
            return

        poll_id = generate_poll_id()

        poll = create_poll(
            poll_id=poll_id,
            question=question,
            options=opts,
            creator_id=interaction.user.id,
            multiple=True,
            duration_minutes=0,
            notify_roles=list(config.DEFAULT_POLL_NOTIFY_ROLES or [])
        )

        poll["guild_id"] = interaction.guild.id

        await interaction.response.send_message(
            embed=build_poll_embed(poll),
            view=PollView(poll)
        )

        msg = await interaction.original_response()
        poll["message_id"] = msg.id
        poll["channel_id"] = msg.channel.id

        from modules.polls.storage import save_poll
        save_poll(poll)

        from modules.polls.polls_db import create_poll as db_create_poll
        db_create_poll(poll)

        log(f"POLL created id={poll_id}", "POLL")
        

    @tree.command(name="poll_help", guild=discord.Object(id=GUILD_ID))
    async def poll_help(interaction: discord.Interaction):
        from ui.embed_factory import sauron_embed, EMBED_COLOR_INFO

        embed = sauron_embed(
            title="📊 PollBot — Aide rapide staff",
            description=(
                "**Créer un sondage**\n"
                "`/poll question: Texte options: Choix1;Choix2;Choix3`\n\n"
                "→ N’oubliez pas le ; entre chaque Choix\n\n"

                "**Statut d’un sondage**\n"
                "`/poll_status poll_id: XXXXXXXX`\n"
                "→ Résumé, votes par choix et absents\n\n"

                "**Fermer un sondage**\n"
                "`/poll_close poll_id: XXXXXXXX`\n"
                "*(ID en bas du sondage)*\n\n"

                "**Absences**\n"
                "`/poll_absences`\n"
                "`/poll_absences_reset_user @User`\n"
                "`/poll_absences_reset_all`\n\n"

                "**Boutons sur le sondage**\n"
                "⏱️ Durée • 📣 Notifier absents\n\n"

                "*Commandes admin uniquement*"
            ),
            color=EMBED_COLOR_INFO
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =========================
    # /poll_absences
    # =========================
    @tree.command(name="poll_absences", guild=discord.Object(id=GUILD_ID))
    async def poll_absences(interaction: discord.Interaction):
        data = load_non_voters()
        if not data:
            await interaction.response.send_message(
                "✅ Aucune absence enregistrée",
                ephemeral=True
            )
            return

        lines = [
            f"<@{uid}> : {count} absence(s)"
            for uid, count in data.items()
        ]

        await interaction.response.send_message(
            "**📋 Absences de votes :**\n" + "\n".join(lines),
            ephemeral=True
        )

    # =========================
    # /poll_close
    # =========================
    @tree.command(name="poll_close", guild=discord.Object(id=GUILD_ID))
    async def poll_close(
        interaction: discord.Interaction,
        poll_id: str
    ):
        member = interaction.guild.get_member(interaction.user.id)

        if not member or not any(
            role.id in config.ADMIN_ROLE_IDS
            for role in member.roles
        ):
            await interaction.response.send_message(
                "❌ Commande réservée aux administrateurs",
                ephemeral=True
            )
            return

        from modules.polls.scheduler import close_poll_and_process

        await close_poll_and_process(
            interaction.client,
            poll_id,
            reason="manual"
        )

        await interaction.response.send_message(
            f"🔒 Sondage `{poll_id}` fermé manuellement",
            ephemeral=True
        )

    # =========================
    # /poll_absences_reset
    # =========================
    @tree.command(name="poll_absences_reset_user", guild=discord.Object(id=GUILD_ID))
    @app_commands.describe(
        member="Utilisateur à retirer de la base des absents"
    )
    async def poll_absences_reset_user(
        interaction: discord.Interaction,
        member: discord.Member
    ):
        # Vérif admin
        author = interaction.guild.get_member(interaction.user.id)
        if not author or not any(
            r.id in config.ADMIN_ROLE_IDS for r in author.roles
        ):
            return await interaction.response.send_message(
                "❌ Commande réservée aux administrateurs",
                ephemeral=True
            )

        success = reset_user_absences(member.id)

        if success:
            await interaction.response.send_message(
                f"✅ **{member.display_name}** a été retiré de la base des absents.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ **{member.display_name}** n’était pas présent dans la base.",
                ephemeral=True
            )

    @tree.command(name="poll_absences_reset_all", guild=discord.Object(id=GUILD_ID))
    async def poll_absences_reset_all(interaction: discord.Interaction):
        # Vérif admin
        author = interaction.guild.get_member(interaction.user.id)
        if not author or not any(
            r.id in config.ADMIN_ROLE_IDS for r in author.roles
        ):
            return await interaction.response.send_message(
                "❌ Commande réservée aux administrateurs",
                ephemeral=True
            )

        reset_all_absences()

        await interaction.response.send_message(
            "🧹 **La base des absents a été entièrement réinitialisée.**",
            ephemeral=True
        )

    # =========================
    # /poll_status
    # =========================

    @tree.command(name="poll_status", guild=discord.Object(id=GUILD_ID))
    @app_commands.describe(poll_id="ID du sondage")
    async def poll_status(interaction: discord.Interaction, poll_id: str):
        await interaction.response.defer(ephemeral=True)

        # 🔒 Admin only
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not any(r.id in config.ADMIN_ROLE_IDS for r in member.roles):
            return await interaction.followup.send(
                "❌ Commande réservée aux administrateurs",
                ephemeral=True
            )

        poll = get_poll(poll_id)
        if not poll:
            return await interaction.followup.send(
                "❌ Sondage introuvable",
                ephemeral=True
            )

        guild = interaction.guild
        votes = get_votes(poll_id)  # { option: [user_id] }

        # =========================
        # Construire votes par option
        # =========================
        vote_lines_by_option = {}
        all_voters = set()

        for option, user_ids in votes.items():
            lines = []
            for uid in user_ids:
                m = guild.get_member(uid)
                if m:
                    lines.append(m.mention)
                    all_voters.add(uid)
            vote_lines_by_option[option] = lines

        # =========================
        # Construire absents
        # =========================
        notify_roles = poll.get("notify_roles") or config.DEFAULT_POLL_NOTIFY_ROLES or []
        missing = []

        async for m in guild.fetch_members(limit=None):
            if m.bot:
                continue
            if not any(r.id in notify_roles for r in m.roles):
                continue
            if m.id not in all_voters:
                missing.append(m.mention)

        # =========================
        # EMBED 1 — RÉSUMÉ
        # =========================
        total_votes = sum(len(v) for v in vote_lines_by_option.values())

        summary = discord.Embed(
            title="📊 Statut du sondage",
            description=poll["question"],
            color=discord.Color.dark_teal()
        )
        summary.add_field(name="🗳️ Votants", value=str(total_votes), inline=True)
        summary.add_field(name="🚫 Absents", value=str(len(missing)), inline=True)
        summary.add_field(
            name="🔁 Multi-vote",
            value="Activé" if poll.get("multiple", True) else "Désactivé",
            inline=True
        )
        summary.set_footer(text=f"ID : {poll_id} • Sauron")

        embeds = [summary]

        # =========================
        # EMBEDS — VOTES PAR OPTION
        # =========================
        for option, users in vote_lines_by_option.items():
            pages = paginate(users, 15)
            for i, page in enumerate(pages):
                e = discord.Embed(
                    title=f"🗳️ {option} — {len(users)} vote(s)",
                    description="\n".join(page) if page else "Aucun vote",
                    color=discord.Color.blurple()
                )
                e.set_footer(text=f"Page {i+1}/{len(pages)} • Option {option}")
                embeds.append(e)

        # =========================
        # EMBEDS — ABSENTS
        # =========================
        if missing:
            pages = paginate(missing, 15)
            for i, page in enumerate(pages):
                e = discord.Embed(
                    title=f"🚫 N'ont pas voté — {len(missing)}",
                    description="\n".join(page),
                    color=discord.Color.red()
                )
                e.set_footer(text=f"Page {i+1}/{len(pages)}")
                embeds.append(e)

        # =========================
        # ENVOI
        # =========================
        view = PollStatusView(embeds)
        await interaction.followup.send(
            embed=embeds[0],
            view=view,
            ephemeral=True
        )

def setup(tree, guild_id):
    module_log("polls", "registering commands")
    setup_poll_commands(tree, guild_id)
