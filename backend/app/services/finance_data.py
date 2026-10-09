from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

DATA_DIRECTORY = Path(
    os.environ.get(
        "ORBITIQ_FINANCE_DATA_DIR",
        str(Path(__file__).resolve().parents[1] / "data" / "finance"),
    )
)
DATABASE_PATH = Path(os.environ.get("ORBITIQ_FINANCE_DB_PATH", str(DATA_DIRECTORY / "finance.db")))
TABLE_FILES = {
    "invoices": "invoices.csv",
    "invoice_lines": "invoice_lines.csv",
    "invoice_exceptions": "invoice_exceptions.csv",
    "purchase_orders": "purchase_orders.csv",
    "suppliers": "suppliers.csv",
    "payments": "payments.csv",
}
_BATCH_SIZE = 5000
_INITIALIZATION_LOCK = threading.Lock()


def _source_signature() -> str:
    signature = {
        filename: (DATA_DIRECTORY / filename).stat().st_size
        for filename in TABLE_FILES.values()
    }
    return json.dumps(signature, sort_keys=True)


def _database_is_current(signature: str) -> bool:
    if not DATABASE_PATH.is_file():
        return False
    try:
        with closing(sqlite3.connect(DATABASE_PATH)) as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'source_signature'"
            ).fetchone()
        return row is not None and row[0] == signature
    except sqlite3.DatabaseError:
        return False


def _create_table(connection: sqlite3.Connection, table: str, filename: str) -> None:
    source_path = DATA_DIRECTORY / filename
    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        if not columns or any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", item) is None for item in columns):
            raise ValueError(f"Invalid CSV header in {filename}")

        column_sql = ", ".join(f'"{column}" TEXT' for column in columns)
        connection.execute(f'CREATE TABLE "{table}" ({column_sql})')
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f'INSERT INTO "{table}" VALUES ({placeholders})'
        batch: list[tuple[str | None, ...]] = []
        for row in reader:
            batch.append(tuple(row.get(column) or None for column in columns))
            if len(batch) >= _BATCH_SIZE:
                connection.executemany(insert_sql, batch)
                batch.clear()
        if batch:
            connection.executemany(insert_sql, batch)


def ensure_finance_database() -> None:
    missing = [filename for filename in TABLE_FILES.values() if not (DATA_DIRECTORY / filename).is_file()]
    if missing:
        raise FileNotFoundError(f"Required curated finance CSVs are missing: {', '.join(missing)}")

    signature = _source_signature()
    if _database_is_current(signature):
        return

    with _INITIALIZATION_LOCK:
        if _database_is_current(signature):
            return

        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = DATABASE_PATH.with_suffix(".building")
        temporary_path.unlink(missing_ok=True)
        try:
            with closing(sqlite3.connect(temporary_path)) as connection:
                for table, filename in TABLE_FILES.items():
                    _create_table(connection, table, filename)

                for table, columns in {
                    "invoices": ("invoice_id", "supplier_id", "po_id", "invoice_number", "invoice_date"),
                    "invoice_lines": ("invoice_id",),
                    "invoice_exceptions": ("invoice_id", "exception_type"),
                    "purchase_orders": ("po_id", "supplier_id"),
                    "suppliers": ("supplier_id",),
                    "payments": ("invoice_id", "paid_at"),
                }.items():
                    for column in columns:
                        connection.execute(
                            f'CREATE INDEX "idx_{table}_{column}" ON "{table}" ("{column}")'
                        )

                connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                connection.execute(
                    "INSERT INTO metadata (key, value) VALUES ('source_signature', ?)",
                    (signature,),
                )
                connection.commit()
            os.replace(temporary_path, DATABASE_PATH)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise


def _connect() -> sqlite3.Connection:
    ensure_finance_database()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _normalize_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result: dict[str, Any] = dict(row)
    for key, value in result.items():
        if value is None:
            continue
        if key in {"gross_amount", "net_amount", "tax_amount", "amount_usd", "po_amount", "quantity", "unit_price", "line_amount", "ocr_confidence", "amount"}:
            result[key] = float(value)
        elif key in {"line_no", "payment_terms_days", "days_vs_due"}:
            result[key] = int(value)
    return result


def get_invoice_context(invoice_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        invoice_row = connection.execute(
            "SELECT * FROM invoices WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()
        invoice = _normalize_row(invoice_row)
        if invoice is None:
            return None

        supplier = _normalize_row(
            connection.execute(
                "SELECT * FROM suppliers WHERE supplier_id = ?",
                (invoice["supplier_id"],),
            ).fetchone()
        ) or {}
        po = _normalize_row(
            connection.execute(
                "SELECT * FROM purchase_orders WHERE po_id = ?",
                (invoice.get("po_id"),),
            ).fetchone()
        )
        exceptions = [
            _normalize_row(row) or {}
            for row in connection.execute(
                "SELECT * FROM invoice_exceptions WHERE invoice_id = ? ORDER BY raised_at",
                (invoice_id,),
            ).fetchall()
        ]
        for exception in exceptions:
            exception["type"] = exception.get("exception_type") or "Unspecified exception"
            exception["description"] = exception.get("resolution") or exception["type"]

        invoice_lines = [
            _normalize_row(row) or {}
            for row in connection.execute(
                "SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY line_no LIMIT 50",
                (invoice_id,),
            ).fetchall()
        ]
        payments = [
            _normalize_row(row) or {}
            for row in connection.execute(
                "SELECT * FROM payments WHERE invoice_id = ? ORDER BY paid_at DESC LIMIT 10",
                (invoice_id,),
            ).fetchall()
        ]
        previous_invoices = [
            _normalize_row(row) or {}
            for row in connection.execute(
                """
                SELECT invoice_id, invoice_number, invoice_date, gross_amount, amount_usd, currency, status
                FROM invoices
                WHERE supplier_id = ? AND invoice_id != ?
                ORDER BY invoice_date DESC
                LIMIT 20
                """,
                (invoice["supplier_id"], invoice_id),
            ).fetchall()
        ]
        duplicate_matches = [
            _normalize_row(row) or {}
            for row in connection.execute(
                """
                SELECT invoice_id, supplier_id, invoice_number, invoice_date, status
                FROM invoices
                WHERE supplier_id = ? AND invoice_number = ? AND invoice_id != ?
                ORDER BY invoice_date DESC
                LIMIT 20
                """,
                (invoice["supplier_id"], invoice["invoice_number"], invoice_id),
            ).fetchall()
        ]
        supplier["exception_history"] = connection.execute(
            """
            SELECT COUNT(*)
            FROM invoice_exceptions AS exceptions
            JOIN invoices ON invoices.invoice_id = exceptions.invoice_id
            WHERE invoices.supplier_id = ?
            """,
            (invoice["supplier_id"],),
        ).fetchone()[0]

    invoice["payment_status"] = "paid" if payments else str(invoice.get("status", "unknown")).lower()
    return {
        "invoice": invoice,
        "supplier": supplier,
        "po": po,
        "exceptions": exceptions,
        "invoice_lines": invoice_lines,
        "payments": payments,
        "previous_invoices": previous_invoices,
        "duplicate_matches": duplicate_matches,
    }


def list_invoices(query: str = "", limit: int = 25) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(limit, 100))
    with closing(_connect()) as connection:
        if query.strip():
            pattern = f"%{query.strip()}%"
            rows = connection.execute(
                """
                SELECT invoices.invoice_id, suppliers.supplier_name, invoices.gross_amount, invoices.currency, invoices.status
                FROM invoices
                LEFT JOIN suppliers ON suppliers.supplier_id = invoices.supplier_id
                WHERE invoices.invoice_id LIKE ? OR suppliers.supplier_name LIKE ? OR invoices.invoice_number LIKE ?
                ORDER BY invoices.invoice_id
                LIMIT ?
                """,
                (pattern, pattern, pattern, bounded_limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT invoices.invoice_id, suppliers.supplier_name, invoices.gross_amount, invoices.currency, invoices.status
                FROM invoices
                LEFT JOIN suppliers ON suppliers.supplier_id = invoices.supplier_id
                ORDER BY invoices.invoice_id LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
    return [_normalize_row(row) or {} for row in rows]


def get_invoice_count() -> int:
    with closing(_connect()) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0])