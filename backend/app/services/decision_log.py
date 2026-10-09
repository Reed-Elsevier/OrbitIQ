from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DATABASE_PATH = Path(
    os.environ.get(
        "ORBITIQ_DECISIONS_DB",
        str(Path(__file__).resolve().parents[1] / "data" / "decisions.db"),
    )
)


def _open_database() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'escalate')),
            created_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def record_decision(invoice_id: str, action: str) -> dict[str, int | str]:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_open_database()) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO decisions (invoice_id, action, created_at) VALUES (?, ?, ?)",
            (invoice_id, action, created_at),
        )
        decision_id = cursor.lastrowid

    return {
        "id": decision_id,
        "invoice_id": invoice_id,
        "action": action,
        "created_at": created_at,
    }


def list_decisions(invoice_id: str | None = None) -> list[dict[str, int | str]]:
    query = "SELECT id, invoice_id, action, created_at FROM decisions"
    parameters: tuple[str, ...] = ()
    if invoice_id is not None:
        query += " WHERE invoice_id = ?"
        parameters = (invoice_id,)
    query += " ORDER BY id DESC"

    with closing(_open_database()) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]