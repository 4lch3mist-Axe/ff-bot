import json
import os
import datetime

FILE_PATH = "data/polls/non_voters.json"
os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)


def load_non_voters():
    if not os.path.exists(FILE_PATH):
        return {}
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_non_voters(data):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def register_missed_vote(member, guild):
    data = load_non_voters()
    uid = str(member.id)

    # 🔑 source de vérité = user_id
    entry = data.get(uid)

    if not entry:
        entry = {
            "user_id": uid,
            "display_name": member.display_name,
            "server_name": guild.name,
            "missed_votes": 0,
            "last_missed": None
        }

    # 🔄 MAJ dynamique à CHAQUE appel
    entry["display_name"] = member.display_name
    entry["server_name"] = guild.name
    entry["missed_votes"] += 1
    entry["last_missed"] = (
        datetime.datetime.utcnow().isoformat() + "Z"
    )

    data[uid] = entry
    save_non_voters(data)

def reset_user_absences(user_id: int):
    data = load_non_voters()
    uid = str(user_id)

    if uid in data:
        del data[uid]
        save_non_voters(data)
        return True

    return False


def reset_all_absences():
    save_non_voters({})

