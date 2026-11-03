"""SQLite event store for received webhooks."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Event:
    id: str
    source: str
    received_at: str
    body: bytes
    headers: dict[str, str]
    replay_status: str
    replay_detail: str | None


class EventStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    headers_json TEXT NOT NULL,
                    body_blob BLOB NOT NULL,
                    replay_status TEXT NOT NULL,
                    replay_detail TEXT
                )
                """
            )
            conn.commit()

    def insert(self, source: str, body: bytes, headers: dict) -> Event:
        event_id = str(uuid.uuid4())
        received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        headers_dict = {str(k): str(v) for k, v in headers.items()}
        event = Event(
            id=event_id,
            source=source,
            received_at=received_at,
            body=body,
            headers=headers_dict,
            replay_status="none",
            replay_detail=None,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    id, source, received_at, headers_json, body_blob,
                    replay_status, replay_detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.source,
                    event.received_at,
                    json.dumps(event.headers),
                    event.body,
                    event.replay_status,
                    event.replay_detail,
                ),
            )
            conn.commit()
        return event

    def get(self, id: str) -> Event | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_event(row)

    def list_events(
        self, *, source: str | None = None, limit: int = 50
    ) -> list[Event]:
        with self._connect() as conn:
            if source is None:
                rows = conn.execute(
                    """
                    SELECT * FROM events
                    ORDER BY received_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM events
                    WHERE source = ?
                    ORDER BY received_at DESC
                    LIMIT ?
                    """,
                    (source, limit),
                ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def update_replay(
        self, id: str, status: str, detail: str | None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE events
                SET replay_status = ?, replay_detail = ?
                WHERE id = ?
                """,
                (status, detail, id),
            )
            conn.commit()

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        headers = json.loads(row["headers_json"])
        body = row["body_blob"]
        if not isinstance(body, (bytes, bytearray)):
            body = bytes(body)
        return Event(
            id=row["id"],
            source=row["source"],
            received_at=row["received_at"],
            body=bytes(body),
            headers=headers,
            replay_status=row["replay_status"],
            replay_detail=row["replay_detail"],
        )
