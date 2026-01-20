import datetime
import os
import shutil
import time
import uuid


from polls.storage import load_poll, save_poll
from polls.polls_db import register_vote as db_register_vote
from polls.polls_db import remove_vote as db_remove_vote

ACTIVE_DIR = "data/polls/active"
ARCHIVE_DIR = "data/polls/archive"

DEFAULT_RETENTION_DAYS = 30

os.makedirs(ACTIVE_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# =========================
# UTILS
# =========================
def now():
    return datetime.datetime.utcnow()

def active_path(poll_id):
    return os.path.join(ACTIVE_DIR, f"poll_{poll_id}.json")

def archive_path(poll_id):
    return os.path.join(ARCHIVE_DIR, f"poll_{poll_id}.json")

def generate_poll_id() -> str:
    return uuid.uuid4().hex[:8]

# =========================
# CLEANUP
# =========================
def cleanup_archives(retention_days=DEFAULT_RETENTION_DAYS):
    limit = time.time() - retention_days * 86400
    for f in os.listdir(ARCHIVE_DIR):
        path = os.path.join(ARCHIVE_DIR, f)
        if os.path.isfile(path) and os.path.getmtime(path) < limit:
            os.remove(path)

# =========================
# ARCHIVE
# =========================
def archive_poll(poll_id):
    src = active_path(poll_id)
    dst = archive_path(poll_id)

    if os.path.exists(src):
        shutil.move(src, dst)

    cleanup_archives()

# =========================
# CORE LOGIC
# =========================
def create_poll(
    poll_id: str,
    question: str,
    options: list,
    creator_id: int,
    multiple: bool = True,
    duration_minutes: int = 0,
    notify_roles: list | None = None
):
    ends_at = None
    if duration_minutes > 0:
        ends_at = (now() + datetime.timedelta(minutes=duration_minutes)).isoformat()

    poll = {
        "poll_id": poll_id,
        "question": question,
        "options": options,
        "created_by": creator_id,
        "created_at": now().isoformat(),
        "status": "open",
        "multiple": multiple,
        "duration_minutes": duration_minutes,
        "ends_at": ends_at,
        "notify_roles": notify_roles or [],
        "alert_sent": False,
        "votes": {},
        "message_id": None,
        "channel_id": None
    }

    save_poll(poll)
    return poll

def register_vote(poll_id, user_id, option):
    poll = load_poll(poll_id)
    if not poll:
        return None, "closed", None

    if poll.get("ends_at"):
        ends_at = datetime.datetime.fromisoformat(poll["ends_at"])
        if now() >= ends_at:
            poll["status"] = "closed"
            save_poll(poll)
            archive_poll(poll_id)
            return poll, "closed", None

    if poll["status"] != "open":
        return poll, "closed", None

    uid = str(user_id)
    votes = poll["votes"].get(uid, [])
    action = None

    if poll["multiple"]:
        if option in votes:
            votes.remove(option)
            action = "removed"
        else:
            votes.append(option)
            action = "added"

        if votes:
            poll["votes"][uid] = votes
        else:
            poll["votes"].pop(uid, None)
    else:
        if votes and votes[0] == option:
            poll["votes"].pop(uid, None)
            action = "removed"
        else:
            poll["votes"][uid] = [option]
            action = "added"

    save_poll(poll)

    if action == "added":
        db_register_vote(poll_id, user_id, option)
    elif action == "removed":
        db_remove_vote(poll_id, user_id, option)

    return poll, "ok", action

def compute_results(poll):
    counts = {opt: 0 for opt in poll["options"]}
    for votes in poll["votes"].values():
        for v in votes:
            if v in counts:
                counts[v] += 1
    return counts

def set_status(poll_id, status):
    poll = load_poll(poll_id)
    if not poll:
        return None

    poll["status"] = status
    save_poll(poll)

    if status == "closed":
        archive_poll(poll_id)

    return poll
