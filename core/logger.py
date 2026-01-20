# core/logger.py
import datetime

def log(message: str, level: str = "INFO"):
    ts = datetime.datetime.utcnow().isoformat()
    print(f"[{ts}] [{level}] {message}")
