from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from database.db import get_connection


def _rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stock_sort_key(row: dict[str, Any]) -> tuple[float, float, float, int]:
    investment_score = _safe_float(row.get("investment_score"))
    confidence_score = _safe_float(row.get("confidence_score")) or 0
    day5_avg_return = _safe_float(row.get("day5_avg_return"))
    signal_count = int(row.get("signal_count") or 0)
    return (
        investment_score if investment_score is not None else -1,
        confidence_score,
        day5_avg_return if day5_avg_return is not None else -9999,
        signal_count,
    )


def _load_theme_ranking_rows(report_date: date) -> list[dict[str, Any]]:
    sql = """
        WITH latest_analysis AS (
            SELECT DISTINCT ON (stock_name)
                stock_name,
                investment_score,
                investment_grade,
                investment_grade_detail,
                confidence_score,
                analysis_date,
                id
            FROM stock_analysis
            WHERE analysis_date::date = %(report_date)s
            ORDER BY stock_name, analysis_date DESC, id DESC
        )
        SELECT
            se.stock_code,
            sm.stock_name,
            COALESCE(sp.primary_theme, '미분류') AS primary_theme,
            se.trading_value,
            la.investment_score,
            la.investment_grade,
            la.investment_grade_detail,
            la.confidence_score,
            sps.signal_count,
            sps.day5_avg_return
        FROM signal_event se
        JOIN stock_master sm
            ON sm.stock_code = se.stock_code
        LEFT JOIN stock_profile sp
            ON sp.stock_name = sm.stock_name
        LEFT JOIN latest_analysis la
            ON la.stock_name = sm.stock_name
        LEFT JOIN stock_pattern_stats sps
            ON sps.stock_name = sm.stock_name
        WHERE se.signal_date = %(report_date)s
        ORDER BY se.trading_value DESC NULLS LAST, sm.stock_name
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            return _rows_to_dicts(cursor)


def build_theme_rankings(report_date: date) -> list[dict[str, Any]]:
    rows = _load_theme_ranking_rows(report_date)
    if not rows:
        return []

    total_trading_value = sum(
        _safe_float(row.get("trading_value")) or 0
        for row in rows
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        theme = str(row.get("primary_theme") or "미분류").strip() or "미분류"
        grouped[theme].append(row)

    rankings: list[dict[str, Any]] = []
    for theme, theme_rows in grouped.items():
        stock_count = len(theme_rows)
        scores = [
            score
            for score in (_safe_float(row.get("investment_score")) for row in theme_rows)
            if score is not None
        ]
        average_investment_score = sum(scores) / len(scores) if scores else 0
        ab_count = sum(
            1
            for row in theme_rows
            if str(row.get("investment_grade") or "") in {"A", "B"}
        )
        ab_ratio = ab_count / stock_count if stock_count else 0
        theme_trading_value = sum(
            _safe_float(row.get("trading_value")) or 0
            for row in theme_rows
        )
        trading_share = (
            theme_trading_value / total_trading_value
            if total_trading_value > 0
            else 0
        )

        stock_count_score = min(25, stock_count * 5)
        average_score = average_investment_score * 0.35
        grade_score = ab_ratio * 20
        trading_score = trading_share * 20
        theme_score = round(
            min(100, stock_count_score + average_score + grade_score + trading_score)
        )

        ranked_stocks = sorted(theme_rows, key=_stock_sort_key, reverse=True)
        leader_row = ranked_stocks[0]
        followers = ranked_stocks[1:4]

        rankings.append(
            {
                "theme": theme,
                "theme_score": int(theme_score),
                "stock_count": stock_count,
                "leader": leader_row.get("stock_name"),
                "leader_score": _safe_float(leader_row.get("investment_score")),
                "leader_grade": leader_row.get("investment_grade"),
                "stocks": [row.get("stock_name") for row in ranked_stocks],
                "followers": [row.get("stock_name") for row in followers],
                "follower_details": [
                    {
                        "stock_name": row.get("stock_name"),
                        "investment_score": _safe_float(row.get("investment_score")),
                        "investment_grade": row.get("investment_grade"),
                    }
                    for row in followers
                ],
                "average_investment_score": round(average_investment_score, 2),
                "ab_grade_count": ab_count,
                "trading_value": theme_trading_value,
                "trading_share": round(trading_share * 100, 2),
                "score_breakdown": {
                    "stock_count": round(stock_count_score, 2),
                    "average_investment": round(average_score, 2),
                    "ab_grade_ratio": round(grade_score, 2),
                    "trading_concentration": round(trading_score, 2),
                },
            }
        )

    return sorted(
        rankings,
        key=lambda row: (
            row["theme_score"],
            row["stock_count"],
            row["average_investment_score"],
            row["trading_value"],
        ),
        reverse=True,
    )
