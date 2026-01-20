import sqlite3
import json
from datetime import datetime
from core.db import db_path


# =========================================================
# DB INIT
# =========================================================

def init_db():
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS polls (
            poll_id TEXT PRIMARY KEY,
            guild_id INTEGER,
            channel_id INTEGER,
            message_id INTEGER,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ends_at TEXT,
            alert_sent INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            poll_id TEXT,
            user_id INTEGER,
            option TEXT,
            PRIMARY KEY (poll_id, user_id, option)
        )
    """)

    conn.commit()
    conn.close()
# =========================================================
# POLL CRUD
# =========================================================

def create_poll(poll: dict):
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO polls (
            poll_id, guild_id, channel_id, message_id,
            question, options, created_by,
            status, created_at, ends_at, alert_sent
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        poll["poll_id"],
        poll.get("guild_id"),
        poll.get("channel_id"),
        poll.get("message_id"),
        poll["question"],
        json.dumps(poll["options"], ensure_ascii=False),
        poll["created_by"],
        poll["status"],
        poll["created_at"],
        poll.get("ends_at"),
        int(poll.get("alert_sent", False))
    ))

    conn.commit()
    conn.close()

def get_poll(poll_id: str) -> dict | None:
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    cur.execute("SELECT * FROM polls WHERE poll_id = ?", (poll_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "poll_id": row[0],
        "guild_id": row[1],
        "channel_id": row[2],
        "message_id": row[3],
        "question": row[4],
        "options": json.loads(row[5]),
        "created_by": row[6],
        "status": row[7],
        "created_at": row[8],
        "ends_at": row[9],
        "alert_sent": bool(row[10]),
    }

# =========================================================
# VOTES
# =========================================================

def register_vote(poll_id: str, user_id: int, option: str) -> bool:
    """
    Enregistre un vote.
    Retourne False si l'utilisateur a déjà voté.
    """
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO votes (poll_id, user_id, option)
            VALUES (?, ?, ?)
        """, (poll_id, user_id, option))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_votes(poll_id: str) -> dict:
    """
    Retourne les votes sous forme {option: [user_id, ...]}
    """
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    cur.execute("""
        SELECT option, user_id FROM votes
        WHERE poll_id = ?
    """, (poll_id,))

    votes = {}
    for option, user_id in cur.fetchall():
        votes.setdefault(option, []).append(user_id)

    conn.close()
    return votes


def count_votes(poll_id: str) -> dict:
    """
    Retourne {option: count}
    """
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    cur.execute("""
        SELECT option, COUNT(*) FROM votes
        WHERE poll_id = ?
        GROUP BY option
    """, (poll_id,))

    counts = {opt: cnt for opt, cnt in cur.fetchall()}
    conn.close()
    return counts

# =========================================================
# FETCH OPEN POLLS
# =========================================================

def fetch_open_polls_with_deadline():
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    cur.execute("""
        SELECT poll_id, ends_at FROM polls
        WHERE status = 'open' AND ends_at IS NOT NULL
    """)

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "poll_id": poll_id,
            "ends_at": ends_at
        }
        for poll_id, ends_at in rows
    ]

#===============
# REMOVE_VOTE
#===============
def remove_vote(poll_id: str, user_id: int, option: str):
    conn = sqlite3.connect(db_path("polls.db"))
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM votes
        WHERE poll_id = ? AND user_id = ? AND option = ?
    """, (poll_id, user_id, option))

    conn.commit()
    conn.close()