"""SQLite-backed progress, streaks and topic preference."""
from __future__ import annotations

import random
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempt (
    user_id   INTEGER NOT NULL,
    task_id   TEXT    NOT NULL,
    task_no   INTEGER NOT NULL,
    ts        INTEGER NOT NULL,
    correct   INTEGER NOT NULL CHECK (correct IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_attempt_user ON attempt (user_id, task_id);

CREATE TABLE IF NOT EXISTS last_seen (
    user_id   INTEGER PRIMARY KEY,
    task_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pref (
    user_id   INTEGER PRIMARY KEY,
    task_no   INTEGER          -- NULL = все темы вперемешку
);
"""


class Storage:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- writing ------------------------------------------------------------

    def record_attempt(self, user_id: int, task_id: str, task_no: int, correct: bool) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO attempt (user_id, task_id, task_no, ts, correct) VALUES (?, ?, ?, ?, ?)",
                (user_id, task_id, task_no, int(time.time()), 1 if correct else 0),
            )
            c.execute(
                "INSERT INTO last_seen (user_id, task_id) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET task_id = excluded.task_id",
                (user_id, task_id),
            )

    def set_topic(self, user_id: int, task_no: int | None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO pref (user_id, task_no) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET task_no = excluded.task_no",
                (user_id, task_no),
            )

    # --- reading ------------------------------------------------------------

    def topic(self, user_id: int) -> int | None:
        with self._conn() as c:
            row = c.execute("SELECT task_no FROM pref WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None

    def stats(self, user_id: int) -> dict:
        with self._conn() as c:
            total, uniq, correct = c.execute(
                "SELECT COUNT(*), COUNT(DISTINCT task_id), COALESCE(SUM(correct), 0) "
                "FROM attempt WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            per_topic = c.execute(
                "SELECT task_no, COUNT(*), COALESCE(SUM(correct), 0) "
                "FROM attempt WHERE user_id = ? GROUP BY task_no ORDER BY task_no",
                (user_id,),
            ).fetchall()
            recent = [
                r[0]
                for r in c.execute(
                    "SELECT correct FROM attempt WHERE user_id = ? ORDER BY ts DESC, rowid DESC LIMIT 50",
                    (user_id,),
                ).fetchall()
            ]
        streak = 0
        for ok in recent:
            if not ok:
                break
            streak += 1
        return {
            "total_attempts": total,
            "unique_tasks": uniq,
            "correct": correct,
            "accuracy": (correct / total) if total else 0.0,
            "per_topic": [
                {"task_no": n, "total": t, "correct": c_} for n, t, c_ in per_topic
            ],
            "streak": streak,
        }

    def _last_outcome_per_task(self, user_id: int) -> dict[str, bool]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT task_id, correct FROM attempt WHERE user_id = ? AND ts = ("
                "  SELECT MAX(ts) FROM attempt a2 "
                "  WHERE a2.user_id = attempt.user_id AND a2.task_id = attempt.task_id)",
                (user_id,),
            ).fetchall()
        return {tid: bool(ok) for tid, ok in rows}

    def _previous_task_id(self, user_id: int) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT task_id FROM last_seen WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None

    # --- selection ----------------------------------------------------------

    def pick_next(self, user_id: int, task_ids: list[str]) -> str | None:
        """Unseen first, then tasks last answered wrong, then the rest."""
        if not task_ids:
            return None
        last = self._previous_task_id(user_id)
        outcomes = self._last_outcome_per_task(user_id)

        unseen = [t for t in task_ids if t not in outcomes and t != last]
        wrong = [t for t in task_ids if outcomes.get(t) is False and t != last]
        right = [t for t in task_ids if outcomes.get(t) is True and t != last]

        roll = random.random()
        if unseen and (roll < 0.7 or not wrong):
            return random.choice(unseen)
        if wrong and roll < 0.95:
            return random.choice(wrong)
        if right:
            return random.choice(right)
        return random.choice(task_ids)
