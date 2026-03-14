"""
Session storage and message queue — lightweight JSON-based persistence
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

SESSIONS_FILE = DATA_DIR / "sessions.json"
QUEUE_FILE = DATA_DIR / "queue.json"


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def _save(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ─── Session Store ────────────────────────────────────────────────────────────

class SessionStore:
    """Persists user goals, state, and processing stats."""

    def _data(self) -> dict:
        return _load(SESSIONS_FILE)

    def _write(self, data: dict):
        _save(SESSIONS_FILE, data)

    def _user(self, user_id: int) -> dict:
        data = self._data()
        uid = str(user_id)
        if uid not in data:
            data[uid] = {
                "goals": None,
                "state": None,
                "stats": {"total": 0, "relevant": 0, "irrelevant": 0, "notes_created": 0},
                "created_at": datetime.now().isoformat(),
            }
            self._write(data)
        return data[uid]

    def get_goals(self, user_id: int) -> Optional[str]:
        return self._user(user_id).get("goals")

    def save_goals(self, user_id: int, goals: str):
        data = self._data()
        uid = str(user_id)
        if uid not in data:
            self._user(user_id)  # initialize
            data = self._data()
        data[uid]["goals"] = goals
        data[uid]["goals_updated_at"] = datetime.now().isoformat()
        self._write(data)
        logger.info(f"Goals saved for user {user_id}")

    def get_state(self, user_id: int) -> Optional[str]:
        return self._user(user_id).get("state")

    def set_state(self, user_id: int, state: Optional[str]):
        data = self._data()
        uid = str(user_id)
        if uid not in data:
            self._user(user_id)
            data = self._data()
        data[uid]["state"] = state
        self._write(data)

    def get_stats(self, user_id: int) -> dict:
        return self._user(user_id).get("stats", {})

    def record_processed(self, user_id: int, is_relevant: bool):
        data = self._data()
        uid = str(user_id)
        if uid not in data:
            self._user(user_id)
            data = self._data()
        s = data[uid].setdefault("stats", {"total": 0, "relevant": 0, "irrelevant": 0, "notes_created": 0})
        s["total"] += 1
        s["notes_created"] += 1
        if is_relevant:
            s["relevant"] += 1
        else:
            s["irrelevant"] += 1
        self._write(data)


# ─── Message Queue ────────────────────────────────────────────────────────────

class MessageQueue:
    """Simple persistent queue for link processing jobs."""

    def _data(self) -> list:
        d = _load(QUEUE_FILE)
        return d.get("items", [])

    def _write(self, items: list):
        _save(QUEUE_FILE, {"items": items, "updated_at": datetime.now().isoformat()})

    def add(self, url: str, user_id: int):
        items = self._data()
        items.append({
            "url": url,
            "user_id": user_id,
            "status": "pending",
            "added_at": datetime.now().isoformat(),
            "attempts": 0,
        })
        self._write(items)

    def mark_done(self, url: str):
        items = self._data()
        for item in items:
            if item["url"] == url:
                item["status"] = "done"
                item["done_at"] = datetime.now().isoformat()
        self._write(items)

    def mark_failed(self, url: str):
        items = self._data()
        for item in items:
            if item["url"] == url:
                item["status"] = "failed"
                item["attempts"] = item.get("attempts", 0) + 1
        self._write(items)

    def get_all(self) -> list:
        return self._data()

    def get_pending(self) -> list:
        return [i for i in self._data() if i["status"] == "pending"]
