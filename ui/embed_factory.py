# ==============================
# 🎨 CHARTE VISUELLE SAURON
# ==============================

import discord

EMBED_COLOR_MAIN = 0x8B0000
EMBED_COLOR_INFO = 0x2B2B2B
EMBED_COLOR_WARN = 0xFF8C00

FOOTER_TEXT = "Sauron • Observation active"

def sauron_embed(
    *,
    title: str | None = None,
    description: str | None = None,
    color: int = EMBED_COLOR_MAIN
) -> discord.Embed:

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed
