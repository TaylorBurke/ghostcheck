"""Local SQLite snapshots, so repeated checks can spot long-open or reposted roles."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
from datetime import date
from pathlib import Path

from .models import Posting


def default_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "ghostcheck" / "history.db"


def fingerprint(p: Posting) -> str:
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return hashlib.sha1(f"{norm(p.company)}|{norm(p.title)}|{norm(p.location)}".encode()).hexdigest()[:16]


class History:
    def __init__(self, path: Path | None = None):
        self.path = path or default_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # checks may run in worker threads
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS seen (fp TEXT, url TEXT, seen_on TEXT, date_posted TEXT, "
            "PRIMARY KEY (fp, url, seen_on))"
        )

    def record(self, p: Posting, today: date) -> None:
        with self._lock:
            self.db.execute(
                "INSERT OR IGNORE INTO seen VALUES (?,?,?,?)",
                (fingerprint(p), p.url, today.isoformat(), p.date_posted.isoformat() if p.date_posted else None),
            )
            self.db.commit()

    def first_seen(self, p: Posting) -> date | None:
        with self._lock:
            row = self.db.execute("SELECT MIN(seen_on) FROM seen WHERE fp=?", (fingerprint(p),)).fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None

    def distinct_urls(self, p: Posting) -> int:
        """Same role seen under several URLs/ids is a repost signal."""
        with self._lock:
            return self.db.execute("SELECT COUNT(DISTINCT url) FROM seen WHERE fp=?", (fingerprint(p),)).fetchone()[0]
