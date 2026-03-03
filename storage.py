#!/usr/bin/env python3
"""SQLite storage for agents and messages."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".hive" / "hive.db"


class Storage:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                topic_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('in', 'out')),
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                telegram_message_id INTEGER,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def register_agent(self, agent_id: str, name: str, topic_id: int):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO agents (id, name, topic_id, created_at) VALUES (?, ?, ?, ?)",
            (agent_id, name, topic_id, now),
        )
        self.conn.commit()

    def get_agent(self, agent_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_agent_by_topic(self, topic_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM agents WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        return dict(row) if row else None

    def save_message(
        self,
        agent_id: str,
        direction: str,
        text: str,
        telegram_message_id: int = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            "INSERT INTO messages (agent_id, direction, text, timestamp, telegram_message_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (agent_id, direction, text, now, telegram_message_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_messages(
        self, agent_id: str, limit: int = 20, since_id: int = None
    ) -> list[dict]:
        if since_id:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE agent_id = ? AND direction = 'in' AND id > ? "
                "ORDER BY id DESC LIMIT ?",
                (agent_id, since_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE agent_id = ? AND direction = 'in' "
                "ORDER BY id DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_update_offset(self) -> int | None:
        row = self.conn.execute(
            "SELECT value FROM state WHERE key = 'update_offset'"
        ).fetchone()
        return int(row["value"]) if row else None

    def set_update_offset(self, offset: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES ('update_offset', ?)",
            (str(offset),),
        )
        self.conn.commit()
