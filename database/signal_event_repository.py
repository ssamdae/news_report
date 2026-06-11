from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from database.db import get_connection


DEFAULT_SIGNAL_NAME = "500억봉"
DEFAULT_CONDITION_VERSION = "v1"


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _get_signal_date(row: dict[str, Any], signal_date: date | str | None) -> date | str:
    if signal_date is not None:
        return signal_date
    if "signal_date" in row:
        return row["signal_date"]
    if "trade_date" in row:
        return row["trade_date"]
    raise ValueError("signal_date or trade_date is required")


def _build_metadata(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "open_price": _clean_value(row.get("open_price")),
        "high_price": _clean_value(row.get("high_price")),
        "low_price": _clean_value(row.get("low_price")),
        "close_price": _clean_value(row.get("close_price")),
        "prev_close_price": _clean_value(row.get("prev_close_price")),
        "trading_value": _clean_value(row.get("trading_value")),
    }


def _build_signal_rows(
    df: pd.DataFrame,
    signal_name: str,
    condition_version: str,
    signal_date: date | str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in df.to_dict("records"):
        rows.append(
            {
                "signal_date": _get_signal_date(row, signal_date),
                "stock_code": _clean_value(row["stock_code"]),
                "signal_name": signal_name,
                "condition_version": condition_version,
                "trading_value": _clean_value(row.get("trading_value")),
                "close_price": _clean_value(row.get("close_price")),
                "volume": _clean_value(row.get("volume")),
                "metadata": _build_metadata(row),
            }
        )

    return rows


def save_signal_events(
    df: pd.DataFrame,
    signal_date: date | str | None,
    signal_name: str = DEFAULT_SIGNAL_NAME,
    condition_version: str = DEFAULT_CONDITION_VERSION,
) -> int:
    if df.empty:
        return 0
    if "stock_code" not in df.columns:
        raise ValueError("stock_code is required")

    from psycopg.types.json import Jsonb

    rows = _build_signal_rows(df, signal_name, condition_version, signal_date)
    db_rows = [{**row, "metadata": Jsonb(row["metadata"])} for row in rows]

    sql = """
        INSERT INTO signal_event (
            signal_date,
            stock_code,
            signal_name,
            condition_version,
            trading_value,
            close_price,
            volume,
            metadata
        )
        VALUES (
            %(signal_date)s,
            %(stock_code)s,
            %(signal_name)s,
            %(condition_version)s,
            %(trading_value)s,
            %(close_price)s,
            %(volume)s,
            %(metadata)s
        )
        ON CONFLICT (signal_date, stock_code, signal_name)
        DO UPDATE SET
            condition_version = EXCLUDED.condition_version,
            trading_value = EXCLUDED.trading_value,
            close_price = EXCLUDED.close_price,
            volume = EXCLUDED.volume,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, db_rows)
        connection.commit()

    return len(rows)
