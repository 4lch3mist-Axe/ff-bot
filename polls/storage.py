import json
import os
import threading

LOCK = threading.Lock()

ACTIVE_DIR = "data/polls/active"

def poll_path(poll_id: str) -> str:
    return os.path.join(ACTIVE_DIR, f"poll_{poll_id}.json")

def save_poll(data: dict):
    os.makedirs(ACTIVE_DIR, exist_ok=True)
    with LOCK:
        with open(poll_path(data["poll_id"]), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def load_poll(poll_id: str):
    path = poll_path(poll_id)
    if not os.path.exists(path):
        return None
    with LOCK:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
