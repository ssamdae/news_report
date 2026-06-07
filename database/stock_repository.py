from __future__ import annotations

import pandas as pd

from database.db import get_connection


def _clean_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records_from_dataframe(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    records = df[columns].to_dict("records")
    return [
        {key: _clean_value(value) for key, value in record.items()}
        for record in records
    ]


def load_stock_master_by_code(stock_code: str) -> dict | None:
    sql = """
        SELECT
            stock_code,
            stock_name,
            market
        FROM stock_master
        WHERE stock_code = %(stock_code)s
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_code": stock_code})
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "stock_code": row[0],
        "stock_name": row[1],
        "market": row[2],
    }


def load_active_stock_master(limit: int | None = None) -> pd.DataFrame:
    limit_clause = "LIMIT %(limit)s" if limit is not None else ""
    sql = f"""
        SELECT
            stock_code,
            stock_name,
            market
        FROM stock_master
        WHERE is_active = TRUE
        ORDER BY market, stock_code
        {limit_clause}
    """
    params = {"limit": limit} if limit is not None else None

    with get_connection() as connection:
        return pd.read_sql_query(sql, connection, params=params)


def save_stock_master(df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    rows = (
        df[["stock_code", "stock_name", "market"]]
        .drop_duplicates(subset=["stock_code"])
        .to_dict("records")
    )
    rows = [
        {key: _clean_value(value) for key, value in row.items()}
        for row in rows
    ]

    sql = """
        INSERT INTO stock_master (stock_code, stock_name, market)
        VALUES (%(stock_code)s, %(stock_name)s, %(market)s)
        ON CONFLICT (stock_code)
        DO UPDATE SET
            stock_name = EXCLUDED.stock_name,
            market = EXCLUDED.market,
            is_active = TRUE,
            updated_at = NOW()
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, rows)
        connection.commit()

    return len(rows)


def upsert_stock_master_bulk(df: pd.DataFrame) -> int:
    return save_stock_master(df)


def save_daily_prices(df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    rows = _records_from_dataframe(
        df,
        [
            "stock_code",
            "trade_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "prev_close_price",
            "volume",
            "trading_value",
        ],
    )

    sql = """
        INSERT INTO daily_price (
            stock_code,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            prev_close_price,
            volume,
            trading_value
        )
        VALUES (
            %(stock_code)s,
            %(trade_date)s,
            %(open_price)s,
            %(high_price)s,
            %(low_price)s,
            %(close_price)s,
            %(prev_close_price)s,
            %(volume)s,
            %(trading_value)s
        )
        ON CONFLICT (stock_code, trade_date)
        DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            prev_close_price = EXCLUDED.prev_close_price,
            volume = EXCLUDED.volume,
            trading_value = EXCLUDED.trading_value,
            updated_at = NOW()
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, rows)
        connection.commit()

    return len(rows)
