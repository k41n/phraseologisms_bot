"""SQLite-backed progress tracking and weighted task selection."""
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
    task_id   INTEGER NOT NULL,
    ts        INTEGER NOT NULL,
    correct   INTEGER NOT NULL CHECK (correct IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_attempt_user ON attempt (user_id, task_id);

CREATE TABLE IF NOT EXISTS last_seen (
    user_id   INTEGER PRIMARY KEY,
    task_id   INTEGER NOT NULL
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

    # --- writing -------------------------------------------------------------

    def record_attempt(self, user_id: int, task_id: int, correct: bool) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO attempt (user_id, task_id, ts, correct) VALUES (?, ?, ?, ?)",
                (user_id, task_id, int(time.time()), 1 if correct else 0),
            )
            c.execute(
                "INSERT INTO last_seen (user_id, task_id) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET task_id = excluded.task_id",
                (user_id, task_id),
            )

    # --- reading -------------------------------------------------------------

    def stats(self, user_id: int) -> dict:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) total, "
                "       COUNT(DISTINCT task_id) unique_tasks, "
                "       COALESCE(SUM(correct), 0) correct "
                "FROM attempt WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        total, unique_tasks, correct = row
        return {
            "total_attempts": total,
            "unique_tasks": unique_tasks,
            "correct": correct,
            "accuracy": (correct / total) if total else 0.0,
        }

    def _last_outcome_per_task(self, user_id: int) -> dict[int, bool]:
        """For each task this user touched, was the most recent attempt correct?"""
        with self._conn() as c:
            rows = c.execute(
                "SELECT task_id, correct "
                "FROM attempt "
                "WHERE user_id = ? AND ts = ("
                "  SELECT MAX(ts) FROM attempt a2 "
                "  WHERE a2.user_id = attempt.user_id AND a2.task_id = attempt.task_id"
                ") ",
                (user_id,),
            ).fetchall()
        return {tid: bool(c) for tid, c in rows}

    def _previous_task_id(self, user_id: int) -> int | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT task_id FROM last_seen WHERE user_id = ?", (user_id,)
            ).fetchone()
        return row[0] if row else None

    # --- selection -----------------------------------------------------------

    def pick_next(self, user_id: int, all_task_ids: list[int]) -> int | None:
        """Choose the next task for this user.

        Priority (highest first):
          1. Tasks the user has never seen.
          2. Tasks where the last attempt was wrong.
          3. Tasks the user got right (least-recent first, with shuffle).

        We always avoid repeating the immediately-previous task.
        """
        if not all_task_ids:
            return None
        last = self._previous_task_id(user_id)
        outcomes = self._last_outcome_per_task(user_id)

        unseen = [t for t in all_task_ids if t not in outcomes and t != last]
        wrong = [t for t in all_task_ids if outcomes.get(t) is False and t != last]
        right = [t for t in all_task_ids if outcomes.get(t) is True and t != last]

        # 70% from unseen if any, otherwise 70% from wrong if any, else right.
        roll = random.random()
        if unseen and (roll < 0.7 or not wrong):
            return random.choice(unseen)
        if wrong and roll < 0.95:
            return random.choice(wrong)
        if right:
            return random.choice(right)
        # Pools all empty (e.g. only one task and it's `last`) — just pick anything.
        return random.choice(all_task_ids)
