from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from database.db import get_connection


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def normalize_snapshot_data(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, default=_json_default))


def ensure_report_snapshot_tables() -> None:
    sql = """
        CREATE TABLE IF NOT EXISTS report_stock_snapshot (
            id BIGSERIAL PRIMARY KEY,
            report_date DATE NOT NULL,
            stock_code TEXT,
            stock_name TEXT NOT NULL,
            snapshot_data JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (report_date, stock_name)
        );

        CREATE INDEX IF NOT EXISTS idx_report_stock_snapshot_date
            ON report_stock_snapshot (report_date);

        CREATE TABLE IF NOT EXISTS report_snapshot_meta (
            report_date DATE PRIMARY KEY,
            snapshot_version TEXT NOT NULL DEFAULT 'v1',
            source_mode TEXT NOT NULL DEFAULT 'generated',
            stock_count INTEGER NOT NULL DEFAULT 0,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            note TEXT
        );
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()


def get_report_stock_snapshots(report_date: date) -> list[dict[str, Any]]:
    ensure_report_snapshot_tables()
    sql = """
        SELECT snapshot_data
        FROM report_stock_snapshot
        WHERE report_date = %(report_date)s
        ORDER BY id
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            rows = cursor.fetchall()
    return [dict(row[0]) for row in rows]


def has_report_stock_snapshot(report_date: date) -> bool:
    ensure_report_snapshot_tables()
    sql = """
        SELECT EXISTS (
            SELECT 1
            FROM report_stock_snapshot
            WHERE report_date = %(report_date)s
        )
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            return bool(cursor.fetchone()[0])


def delete_report_stock_snapshots(report_date: date) -> int:
    ensure_report_snapshot_tables()
    sql = """
        DELETE FROM report_stock_snapshot
        WHERE report_date = %(report_date)s
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            deleted_count = cursor.rowcount
        connection.commit()
    return deleted_count


def upsert_report_stock_snapshots(report_date: date, rows: list[dict[str, Any]]) -> int:
    ensure_report_snapshot_tables()
    if not rows:
        upsert_report_snapshot_meta(report_date, 0)
        return 0

    db_rows = []
    for row in rows:
        snapshot_data = normalize_snapshot_data(row)
        signal = snapshot_data.get("signal") or {}
        db_rows.append(
            {
                "report_date": report_date,
                "stock_code": snapshot_data.get("stock_code")
                or signal.get("stock_code"),
                "stock_name": snapshot_data.get("stock_name")
                or signal.get("stock_name"),
                "snapshot_data": Jsonb(snapshot_data),
            }
        )

    sql = """
        INSERT INTO report_stock_snapshot (
            report_date,
            stock_code,
            stock_name,
            snapshot_data
        )
        VALUES (
            %(report_date)s,
            %(stock_code)s,
            %(stock_name)s,
            %(snapshot_data)s
        )
        ON CONFLICT (report_date, stock_name)
        DO UPDATE SET
            stock_code = EXCLUDED.stock_code,
            snapshot_data = EXCLUDED.snapshot_data,
            updated_at = NOW()
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, db_rows)
        connection.commit()

    upsert_report_snapshot_meta(report_date, len(db_rows))
    return len(db_rows)


def upsert_report_snapshot_meta(
    report_date: date,
    stock_count: int,
    source_mode: str = "generated",
    note: str | None = None,
) -> None:
    ensure_sql = """
        CREATE TABLE IF NOT EXISTS report_snapshot_meta (
            report_date DATE PRIMARY KEY,
            snapshot_version TEXT NOT NULL DEFAULT 'v1',
            source_mode TEXT NOT NULL DEFAULT 'generated',
            stock_count INTEGER NOT NULL DEFAULT 0,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            note TEXT
        )
    """
    sql = """
        INSERT INTO report_snapshot_meta (
            report_date,
            source_mode,
            stock_count,
            note
        )
        VALUES (
            %(report_date)s,
            %(source_mode)s,
            %(stock_count)s,
            %(note)s
        )
        ON CONFLICT (report_date)
        DO UPDATE SET
            source_mode = EXCLUDED.source_mode,
            stock_count = EXCLUDED.stock_count,
            updated_at = NOW(),
            note = EXCLUDED.note
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(ensure_sql)
            cursor.execute(
                sql,
                {
                    "report_date": report_date,
                    "source_mode": source_mode,
                    "stock_count": stock_count,
                    "note": note,
                },
            )
        connection.commit()


def get_report_snapshot_meta(report_date: date) -> dict[str, Any] | None:
    ensure_report_snapshot_tables()
    sql = """
        SELECT
            report_date,
            snapshot_version,
            source_mode,
            stock_count,
            generated_at,
            updated_at,
            note
        FROM report_snapshot_meta
        WHERE report_date = %(report_date)s
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
