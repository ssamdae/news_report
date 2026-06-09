from __future__ import annotations

from decimal import Decimal
from typing import Any

from database.db import get_connection


EMPTY_PATTERN_STATS = {
    "signal_count": 0,
    "next_day_win_rate": None,
    "next_day_avg_return": None,
    "day3_win_rate": None,
    "day3_avg_return": None,
    "day5_win_rate": None,
    "day5_avg_return": None,
    "max_return_5d": None,
    "min_return_5d": None,
}


def _rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _round_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_stock_pattern_stats() -> dict[str, Any]:
    stats_sql = """
        WITH signal_counts AS (
            SELECT
                se.stock_code,
                MAX(sm.stock_name) AS stock_name,
                COUNT(*)::integer AS signal_count
            FROM signal_event se
            JOIN stock_master sm
                ON sm.stock_code = se.stock_code
            GROUP BY se.stock_code
        ),
        signal_rows AS (
            SELECT
                se.id AS signal_id,
                se.stock_code,
                sm.stock_name,
                se.signal_date,
                dp.close_price AS signal_close
            FROM signal_event se
            JOIN stock_master sm
                ON sm.stock_code = se.stock_code
            JOIN daily_price dp
                ON dp.stock_code = se.stock_code
                AND dp.trade_date = se.signal_date
            WHERE dp.close_price IS NOT NULL
                AND dp.close_price > 0
        ),
        price_offsets AS (
            SELECT
                sr.signal_id,
                sr.stock_code,
                sr.stock_name,
                sr.signal_date,
                sr.signal_close,
                dp.close_price,
                ROW_NUMBER() OVER (
                    PARTITION BY sr.signal_id
                    ORDER BY dp.trade_date
                ) - 1 AS day_offset
            FROM signal_rows sr
            JOIN daily_price dp
                ON dp.stock_code = sr.stock_code
                AND dp.trade_date >= sr.signal_date
            WHERE dp.close_price IS NOT NULL
                AND dp.close_price > 0
        ),
        signal_returns AS (
            SELECT
                signal_id,
                stock_code,
                MAX(stock_name) AS stock_name,
                MAX(signal_close) AS signal_close,
                MAX(CASE WHEN day_offset = 1 THEN close_price END) AS close_d1,
                MAX(CASE WHEN day_offset = 3 THEN close_price END) AS close_d3,
                MAX(CASE WHEN day_offset = 5 THEN close_price END) AS close_d5,
                MAX(
                    CASE
                        WHEN day_offset BETWEEN 1 AND 5
                        THEN (close_price - signal_close) / signal_close * 100
                    END
                ) AS max_return_5d,
                MIN(
                    CASE
                        WHEN day_offset BETWEEN 1 AND 5
                        THEN (close_price - signal_close) / signal_close * 100
                    END
                ) AS min_return_5d
            FROM price_offsets
            WHERE day_offset <= 5
            GROUP BY signal_id, stock_code
        ),
        calculated_stats AS (
            SELECT
                stock_code,
                MAX(stock_name) AS stock_name,
                AVG(
                    CASE
                        WHEN close_d1 IS NOT NULL
                        THEN CASE WHEN close_d1 > signal_close THEN 100.0 ELSE 0.0 END
                    END
                ) AS next_day_win_rate,
                AVG(
                    CASE
                        WHEN close_d1 IS NOT NULL
                        THEN (close_d1 - signal_close) / signal_close * 100
                    END
                ) AS next_day_avg_return,
                AVG(
                    CASE
                        WHEN close_d3 IS NOT NULL
                        THEN CASE WHEN close_d3 > signal_close THEN 100.0 ELSE 0.0 END
                    END
                ) AS day3_win_rate,
                AVG(
                    CASE
                        WHEN close_d3 IS NOT NULL
                        THEN (close_d3 - signal_close) / signal_close * 100
                    END
                ) AS day3_avg_return,
                AVG(
                    CASE
                        WHEN close_d5 IS NOT NULL
                        THEN CASE WHEN close_d5 > signal_close THEN 100.0 ELSE 0.0 END
                    END
                ) AS day5_win_rate,
                AVG(
                    CASE
                        WHEN close_d5 IS NOT NULL
                        THEN (close_d5 - signal_close) / signal_close * 100
                    END
                ) AS day5_avg_return,
                MAX(max_return_5d) AS max_return_5d,
                MIN(min_return_5d) AS min_return_5d
            FROM signal_returns
            GROUP BY stock_code
        )
        SELECT
            sc.stock_code,
            sc.stock_name,
            sc.signal_count,
            cs.next_day_win_rate,
            cs.next_day_avg_return,
            cs.day3_win_rate,
            cs.day3_avg_return,
            cs.day5_win_rate,
            cs.day5_avg_return,
            cs.max_return_5d,
            cs.min_return_5d
        FROM signal_counts sc
        LEFT JOIN calculated_stats cs
            ON cs.stock_code = sc.stock_code
        ORDER BY sc.stock_code
    """
    upsert_sql = """
        INSERT INTO stock_pattern_stats (
            stock_code,
            stock_name,
            signal_count,
            next_day_win_rate,
            next_day_avg_return,
            day3_win_rate,
            day3_avg_return,
            day5_win_rate,
            day5_avg_return,
            max_return_5d,
            min_return_5d,
            updated_at
        )
        VALUES (
            %(stock_code)s,
            %(stock_name)s,
            %(signal_count)s,
            %(next_day_win_rate)s,
            %(next_day_avg_return)s,
            %(day3_win_rate)s,
            %(day3_avg_return)s,
            %(day5_win_rate)s,
            %(day5_avg_return)s,
            %(max_return_5d)s,
            %(min_return_5d)s,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (stock_code) DO UPDATE
        SET
            stock_name = EXCLUDED.stock_name,
            signal_count = EXCLUDED.signal_count,
            next_day_win_rate = EXCLUDED.next_day_win_rate,
            next_day_avg_return = EXCLUDED.next_day_avg_return,
            day3_win_rate = EXCLUDED.day3_win_rate,
            day3_avg_return = EXCLUDED.day3_avg_return,
            day5_win_rate = EXCLUDED.day5_win_rate,
            day5_avg_return = EXCLUDED.day5_avg_return,
            max_return_5d = EXCLUDED.max_return_5d,
            min_return_5d = EXCLUDED.min_return_5d,
            updated_at = CURRENT_TIMESTAMP
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(stats_sql)
            rows = _rows_to_dicts(cursor)

            normalized_rows = []
            for row in rows:
                normalized_rows.append(
                    {
                        "stock_code": row["stock_code"],
                        "stock_name": row["stock_name"],
                        "signal_count": row["signal_count"] or 0,
                        "next_day_win_rate": _round_decimal(
                            row.get("next_day_win_rate")
                        ),
                        "next_day_avg_return": _round_decimal(
                            row.get("next_day_avg_return")
                        ),
                        "day3_win_rate": _round_decimal(row.get("day3_win_rate")),
                        "day3_avg_return": _round_decimal(row.get("day3_avg_return")),
                        "day5_win_rate": _round_decimal(row.get("day5_win_rate")),
                        "day5_avg_return": _round_decimal(row.get("day5_avg_return")),
                        "max_return_5d": _round_decimal(row.get("max_return_5d")),
                        "min_return_5d": _round_decimal(row.get("min_return_5d")),
                    }
                )

            if normalized_rows:
                cursor.executemany(upsert_sql, normalized_rows)
        connection.commit()

    return {"stock_count": len(rows)}


def get_stock_pattern_stats(stock_name: str) -> dict[str, Any]:
    stock_name = (stock_name or "").strip()
    empty = {"stock_name": stock_name, **EMPTY_PATTERN_STATS}
    if not stock_name:
        return empty

    sql = """
        SELECT
            stock_name,
            signal_count,
            next_day_win_rate,
            next_day_avg_return,
            day3_win_rate,
            day3_avg_return,
            day5_win_rate,
            day5_avg_return,
            max_return_5d,
            min_return_5d
        FROM stock_pattern_stats
        WHERE stock_name = %(stock_name)s
        LIMIT 1
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_name": stock_name})
            row = cursor.fetchone()
            if row is None:
                return empty
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))

    return {
        "stock_name": result.get("stock_name") or stock_name,
        "signal_count": int(result.get("signal_count") or 0),
        "next_day_win_rate": _as_float(result.get("next_day_win_rate")),
        "next_day_avg_return": _as_float(result.get("next_day_avg_return")),
        "day3_win_rate": _as_float(result.get("day3_win_rate")),
        "day3_avg_return": _as_float(result.get("day3_avg_return")),
        "day5_win_rate": _as_float(result.get("day5_win_rate")),
        "day5_avg_return": _as_float(result.get("day5_avg_return")),
        "max_return_5d": _as_float(result.get("max_return_5d")),
        "min_return_5d": _as_float(result.get("min_return_5d")),
    }
