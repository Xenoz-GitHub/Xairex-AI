"""Local SQLite database: schema migrations + tool audit log (spec section 8).

The only module that opens the database file. All statements are parameterized;
no secrets are ever written. One connection shared behind a lock — the engine
thread writes the audit log, tests and future memory readers may query it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

#: Bump together with a new _MIGRATIONS entry.
SCHEMA_VERSION = 2

_MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE IF NOT EXISTS tool_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        tool TEXT NOT NULL,
        arguments TEXT NOT NULL,
        ok INTEGER NOT NULL,
        message TEXT NOT NULL,
        duration_ms REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_tool_runs_ts ON tool_runs(ts);
    """,
    2: """
    CREATE TABLE IF NOT EXISTS profile_facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS conversation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_conversation_created ON conversation_history(created_at);
    """,
}


class Database:
    """Thread-safe wrapper around one SQLite file with simple migrations."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    # ---------------------------------------------------------------- lifecycle

    def connect(self) -> sqlite3.Connection:
        """Open (once) and migrate the database; returns the connection."""
        with self._lock:
            if self._conn is None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(str(self.path), check_same_thread=False)
                self._migrate(connection)
                self._conn = connection
            return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @property
    def schema_version(self) -> int:
        connection = self.connect()
        with self._lock:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])

    def _migrate(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        for target in sorted(_MIGRATIONS):
            if version < target:
                connection.executescript(_MIGRATIONS[target])
                connection.execute(f"PRAGMA user_version = {target}")  # pragma: no cover-friendly (no params allowed)
                version = target
        connection.commit()

    # -------------------------------------------------------------------- audit

    def log_tool_run(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        ok: bool,
        message: str,
        duration_ms: float,
    ) -> None:
        """Append one tool-run row (arguments/message truncated to 500 chars)."""
        connection = self.connect()
        payload = json.dumps(arguments, ensure_ascii=False)[:500]
        with self._lock:
            connection.execute(
                "INSERT INTO tool_runs (ts, tool, arguments, ok, message, duration_ms) VALUES (?, ?, ?, ?, ?, ?)",
                (time.strftime("%Y-%m-%dT%H:%M:%S"), tool, payload, int(ok), message[:500], round(duration_ms, 2)),
            )
            connection.commit()

    def tool_run_count(self) -> int:
        connection = self.connect()
        with self._lock:
            row = connection.execute("SELECT COUNT(*) FROM tool_runs").fetchone()
            return int(row[0])

    def last_tool_run(self) -> dict[str, Any] | None:
        connection = self.connect()
        with self._lock:
            row = connection.execute(
                "SELECT ts, tool, arguments, ok, message, duration_ms FROM tool_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "ts": row[0],
            "tool": row[1],
            "arguments": row[2],
            "ok": bool(row[3]),
            "message": row[4],
            "duration_ms": row[5],
        }

    # ----------------------------------------------------------- profile facts

    def set_profile_fact(self, key: str, value: str) -> None:
        """Store or update a profile fact (e.g., user's name, preferences)."""
        connection = self.connect()
        with self._lock:
            connection.execute(
                "INSERT OR REPLACE INTO profile_facts (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, time.strftime("%Y-%m-%dT%H:%M:%S")),
            )
            connection.commit()

    def get_profile_fact(self, key: str) -> str | None:
        """Retrieve a profile fact by key."""
        connection = self.connect()
        with self._lock:
            row = connection.execute("SELECT value FROM profile_facts WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def all_profile_facts(self) -> dict[str, str]:
        """All profile facts as a dict."""
        connection = self.connect()
        with self._lock:
            rows = connection.execute("SELECT key, value FROM profile_facts ORDER BY key").fetchall()
        return {row[0]: row[1] for row in rows}

    def delete_profile_fact(self, key: str) -> bool:
        """Delete a profile fact; returns True if it existed."""
        connection = self.connect()
        with self._lock:
            cursor = connection.execute("DELETE FROM profile_facts WHERE key = ?", (key,))
            connection.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------- conversation history

    def save_conversation_turn(self, role: str, content: str) -> None:
        """Save one message to conversation history."""
        connection = self.connect()
        with self._lock:
            connection.execute(
                "INSERT INTO conversation_history (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, time.strftime("%Y-%m-%dT%H:%M:%S")),
            )
            connection.commit()

    def load_conversation_history(self, limit: int = 12) -> list[dict[str, str]]:
        """Load last N conversation turns."""
        connection = self.connect()
        with self._lock:
            rows = connection.execute(
                "SELECT role, content FROM conversation_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        # Reverse so oldest is first
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    def clear_conversation_history(self) -> None:
        """Delete all conversation history."""
        connection = self.connect()
        with self._lock:
            connection.execute("DELETE FROM conversation_history")
            connection.commit()
