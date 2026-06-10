from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from database.db import get_connection


STRATEGY_D0 = "D0 종가매수"
STRATEGY_FIRST_BEARISH = "첫 거래량감소 음봉"
STRATEGY_TWO_BEARISH = "거래량감소 연속 2음봉"
STRATEGY_TWO_BEARISH_VOL_DOWN = "연속 2음봉 + 거래량 추가감소"


RESULT_COLUMNS = [
    "strategy_name",
    "stock_code",
    "stock_name",
    "signal_date",
    "entry_date",
    "entry_price",
    "d0_volume",
    "entry_volume",
    "volume_ratio_to_d0",
    "first_bearish_date",
    "second_bearish_date",
    "first_bearish_volume",
    "second_bearish_volume",
    "vol_down_seq",
    "ret_d3",
    "ret_d5",
    "ret_d10",
    "ret_d20",
    "max_ret_20d",
    "min_ret_20d",
    "params_json",
]


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


def _return_pct(future_price: Any, entry_price: Any) -> float | None:
    future = _safe_float(future_price)
    entry = _safe_float(entry_price)
    if future is None or entry is None or entry <= 0:
        return None
    return round((future - entry) / entry * 100, 4)


def _is_bearish(row: dict[str, Any]) -> bool:
    open_price = _safe_float(row.get("open_price"))
    close_price = _safe_float(row.get("close_price"))
    return open_price is not None and close_price is not None and close_price < open_price


def _is_reduced_volume_bearish(
    row: dict[str, Any],
    d0_volume: int,
    volume_ratio: float,
) -> bool:
    volume = int(row.get("volume") or 0)
    return _is_bearish(row) and d0_volume > 0 and volume <= d0_volume * volume_ratio


def _load_signal_events(
    from_date: date,
    to_date: date,
    min_d0_trade_amount: int,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            se.stock_code,
            sm.stock_name,
            se.signal_date,
            dp.volume AS d0_volume,
            dp.close_price AS d0_close_price,
            COALESCE(se.trading_value, dp.trading_value) AS d0_trading_value
        FROM signal_event se
        JOIN stock_master sm
            ON sm.stock_code = se.stock_code
        JOIN daily_price dp
            ON dp.stock_code = se.stock_code
            AND dp.trade_date = se.signal_date
        WHERE se.signal_date BETWEEN %(from_date)s AND %(to_date)s
            AND se.signal_name LIKE '%%500억%%'
            AND COALESCE(se.trading_value, dp.trading_value) >= %(min_amount)s
        ORDER BY se.stock_code, se.signal_date
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {
                    "from_date": from_date,
                    "to_date": to_date,
                    "min_amount": min_d0_trade_amount,
                },
            )
            return _rows_to_dicts(cursor)


def _load_price_rows(
    stock_codes: list[str],
    from_date: date,
    to_date: date,
) -> dict[str, list[dict[str, Any]]]:
    if not stock_codes:
        return {}

    sql = """
        SELECT
            stock_code,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            trading_value
        FROM daily_price
        WHERE stock_code = ANY(%(stock_codes)s)
            AND trade_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY stock_code, trade_date
    """
    rows_by_stock: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {
                    "stock_codes": stock_codes,
                    "from_date": from_date,
                    "to_date": to_date,
                },
            )
            for row in _rows_to_dicts(cursor):
                rows_by_stock[row["stock_code"]].append(row)
    return dict(rows_by_stock)


def _dedupe_events(
    events: list[dict[str, Any]],
    rows_by_stock: dict[str, list[dict[str, Any]]],
    dedupe_window_days: int | None,
) -> list[dict[str, Any]]:
    if not dedupe_window_days or dedupe_window_days <= 0:
        return events

    kept: list[dict[str, Any]] = []
    last_kept_index_by_stock: dict[str, int] = {}
    date_index_by_stock = {
        stock_code: {row["trade_date"]: index for index, row in enumerate(rows)}
        for stock_code, rows in rows_by_stock.items()
    }

    for event in events:
        stock_code = event["stock_code"]
        signal_date = event["signal_date"]
        current_index = date_index_by_stock.get(stock_code, {}).get(signal_date)
        if current_index is None:
            continue
        last_index = last_kept_index_by_stock.get(stock_code)
        if last_index is not None and current_index - last_index <= dedupe_window_days:
            continue
        kept.append(event)
        last_kept_index_by_stock[stock_code] = current_index
    return kept


def _build_result_row(
    strategy_name: str,
    event: dict[str, Any],
    prices: list[dict[str, Any]],
    entry_index: int,
    d0_volume: int,
    holding_days: list[int],
    params: dict[str, Any],
    first_index: int | None = None,
    second_index: int | None = None,
    vol_down_seq: bool | None = None,
) -> dict[str, Any]:
    entry = prices[entry_index]
    entry_price = _safe_float(entry.get("close_price"))
    entry_volume = int(entry.get("volume") or 0)
    result = {
        "strategy_name": strategy_name,
        "stock_code": event["stock_code"],
        "stock_name": event["stock_name"],
        "signal_date": event["signal_date"],
        "entry_date": entry["trade_date"],
        "entry_price": entry_price,
        "d0_volume": d0_volume,
        "entry_volume": entry_volume,
        "volume_ratio_to_d0": (
            round(entry_volume / d0_volume, 6)
            if d0_volume
            else None
        ),
        "first_bearish_date": None,
        "second_bearish_date": None,
        "first_bearish_volume": None,
        "second_bearish_volume": None,
        "vol_down_seq": vol_down_seq,
        "params_json": json.dumps(params, ensure_ascii=False, default=str),
    }

    if first_index is not None:
        first = prices[first_index]
        result["first_bearish_date"] = first["trade_date"]
        result["first_bearish_volume"] = int(first.get("volume") or 0)
    if second_index is not None:
        second = prices[second_index]
        result["second_bearish_date"] = second["trade_date"]
        result["second_bearish_volume"] = int(second.get("volume") or 0)

    for holding_day in holding_days:
        future_index = entry_index + holding_day
        key = f"ret_d{holding_day}"
        result[key] = (
            _return_pct(prices[future_index].get("close_price"), entry_price)
            if future_index < len(prices)
            else None
        )

    future_window = prices[entry_index + 1 : entry_index + 21]
    if future_window and entry_price and entry_price > 0:
        max_high = max(_safe_float(row.get("high_price")) or 0 for row in future_window)
        min_low = min(
            _safe_float(row.get("low_price")) or float("inf")
            for row in future_window
        )
        result["max_ret_20d"] = _return_pct(max_high, entry_price)
        result["min_ret_20d"] = _return_pct(min_low, entry_price)
    else:
        result["max_ret_20d"] = None
        result["min_ret_20d"] = None

    for holding_day in (3, 5, 10, 20):
        result.setdefault(f"ret_d{holding_day}", None)
    return result


def _find_first_reduced_bearish(
    prices: list[dict[str, Any]],
    d0_index: int,
    lookahead_days: int,
    d0_volume: int,
    volume_ratio: float,
) -> int | None:
    end_index = min(len(prices) - 1, d0_index + lookahead_days)
    for index in range(d0_index + 1, end_index + 1):
        if _is_reduced_volume_bearish(prices[index], d0_volume, volume_ratio):
            return index
    return None


def _find_two_reduced_bearish(
    prices: list[dict[str, Any]],
    d0_index: int,
    lookahead_days: int,
    d0_volume: int,
    volume_ratio: float,
    require_volume_down: bool = False,
) -> tuple[int, int, bool] | None:
    end_index = min(len(prices) - 1, d0_index + lookahead_days)
    for first_index in range(d0_index + 1, end_index):
        second_index = first_index + 1
        first = prices[first_index]
        second = prices[second_index]
        if not _is_reduced_volume_bearish(first, d0_volume, volume_ratio):
            continue
        if not _is_reduced_volume_bearish(second, d0_volume, volume_ratio):
            continue
        vol_down_seq = int(second.get("volume") or 0) <= int(first.get("volume") or 0)
        if require_volume_down and not vol_down_seq:
            continue
        return first_index, second_index, vol_down_seq
    return None


def _save_results(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO backtest_500b_two_bearish_result (
            strategy_name,
            stock_code,
            stock_name,
            signal_date,
            entry_date,
            entry_price,
            d0_volume,
            entry_volume,
            volume_ratio_to_d0,
            first_bearish_date,
            second_bearish_date,
            first_bearish_volume,
            second_bearish_volume,
            vol_down_seq,
            ret_d3,
            ret_d5,
            ret_d10,
            ret_d20,
            max_ret_20d,
            min_ret_20d,
            params_json
        )
        VALUES (
            %(strategy_name)s,
            %(stock_code)s,
            %(stock_name)s,
            %(signal_date)s,
            %(entry_date)s,
            %(entry_price)s,
            %(d0_volume)s,
            %(entry_volume)s,
            %(volume_ratio_to_d0)s,
            %(first_bearish_date)s,
            %(second_bearish_date)s,
            %(first_bearish_volume)s,
            %(second_bearish_volume)s,
            %(vol_down_seq)s,
            %(ret_d3)s,
            %(ret_d5)s,
            %(ret_d10)s,
            %(ret_d20)s,
            %(max_ret_20d)s,
            %(min_ret_20d)s,
            %(params_json)s::jsonb
        )
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, rows)
        connection.commit()
    return len(rows)


def _metric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [
        float(row[key])
        for row in rows
        if row.get(key) is not None
    ]


def summarize_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_strategy[row["strategy_name"]].append(row)

    summary = {}
    for strategy_name, strategy_rows in by_strategy.items():
        row_summary: dict[str, Any] = {"count": len(strategy_rows)}
        for holding_day in (3, 5, 10, 20):
            key = f"ret_d{holding_day}"
            values = _metric_values(strategy_rows, key)
            row_summary[f"d{holding_day}_win_rate"] = (
                sum(1 for value in values if value > 0) / len(values) * 100
                if values
                else None
            )
            row_summary[f"d{holding_day}_avg_return"] = (
                sum(values) / len(values)
                if values
                else None
            )
            row_summary[f"d{holding_day}_median_return"] = (
                statistics.median(values)
                if values
                else None
            )

        max_values = _metric_values(strategy_rows, "max_ret_20d")
        min_values = _metric_values(strategy_rows, "min_ret_20d")
        avg_max = sum(max_values) / len(max_values) if max_values else None
        avg_min = sum(min_values) / len(min_values) if min_values else None
        row_summary["avg_max_ret_20d"] = avg_max
        row_summary["avg_min_ret_20d"] = avg_min
        row_summary["profit_loss_ratio"] = (
            avg_max / abs(avg_min)
            if avg_max is not None and avg_min not in (None, 0)
            else None
        )
        row_summary["best_cases"] = sorted(
            strategy_rows,
            key=lambda row: row.get("ret_d20") if row.get("ret_d20") is not None else -9999,
            reverse=True,
        )[:10]
        row_summary["worst_cases"] = sorted(
            strategy_rows,
            key=lambda row: row.get("ret_d20") if row.get("ret_d20") is not None else 9999,
        )[:10]
        summary[strategy_name] = row_summary
    return summary


def _export_csv(rows: list[dict[str, Any]], params: dict[str, Any]) -> Path | None:
    if not rows:
        return None
    output_dir = Path("reports") / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_name = (
        "backtest_500b_two_bearish_"
        f"{params['from_date']}_{params['to_date']}_"
        f"vr{str(params['volume_ratio']).replace('.', 'p')}.csv"
    )
    output_path = output_dir / file_name
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in RESULT_COLUMNS})
    return output_path


def run_500b_two_bearish_backtest(
    from_date: date,
    to_date: date,
    lookahead_days: int = 20,
    volume_ratio: float = 0.3,
    holding_days: list[int] | None = None,
    min_d0_trade_amount: int = 50_000_000_000,
    dedupe_window_days: int | None = None,
    export_csv: bool = False,
    save_to_db: bool = True,
) -> dict[str, Any]:
    holding_days = holding_days or [3, 5, 10, 20]
    params = {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "lookahead_days": lookahead_days,
        "volume_ratio": volume_ratio,
        "holding_days": holding_days,
        "min_d0_trade_amount": min_d0_trade_amount,
        "dedupe_window_days": dedupe_window_days,
    }

    events = _load_signal_events(from_date, to_date, min_d0_trade_amount)
    stock_codes = sorted({event["stock_code"] for event in events})
    price_to_date = to_date + timedelta(days=max(90, (lookahead_days + 20) * 3))
    rows_by_stock = _load_price_rows(stock_codes, from_date, price_to_date)
    events = _dedupe_events(events, rows_by_stock, dedupe_window_days)

    results: list[dict[str, Any]] = []
    skipped_count = 0
    for event in events:
        prices = rows_by_stock.get(event["stock_code"], [])
        date_to_index = {
            row["trade_date"]: index
            for index, row in enumerate(prices)
        }
        d0_index = date_to_index.get(event["signal_date"])
        if d0_index is None:
            skipped_count += 1
            continue
        d0 = prices[d0_index]
        d0_volume = int(d0.get("volume") or 0)
        if d0_volume <= 0:
            skipped_count += 1
            continue

        results.append(
            _build_result_row(
                STRATEGY_D0,
                event,
                prices,
                d0_index,
                d0_volume,
                holding_days,
                params,
            )
        )

        first_bearish = _find_first_reduced_bearish(
            prices,
            d0_index,
            lookahead_days,
            d0_volume,
            volume_ratio,
        )
        if first_bearish is not None:
            results.append(
                _build_result_row(
                    STRATEGY_FIRST_BEARISH,
                    event,
                    prices,
                    first_bearish,
                    d0_volume,
                    holding_days,
                    params,
                    first_index=first_bearish,
                )
            )

        two_bearish = _find_two_reduced_bearish(
            prices,
            d0_index,
            lookahead_days,
            d0_volume,
            volume_ratio,
        )
        if two_bearish is not None:
            first_index, second_index, vol_down_seq = two_bearish
            results.append(
                _build_result_row(
                    STRATEGY_TWO_BEARISH,
                    event,
                    prices,
                    second_index,
                    d0_volume,
                    holding_days,
                    params,
                    first_index=first_index,
                    second_index=second_index,
                    vol_down_seq=vol_down_seq,
                )
            )
            if vol_down_seq:
                results.append(
                    _build_result_row(
                        STRATEGY_TWO_BEARISH_VOL_DOWN,
                        event,
                        prices,
                        second_index,
                        d0_volume,
                        holding_days,
                        params,
                        first_index=first_index,
                        second_index=second_index,
                        vol_down_seq=True,
                    )
                )

    saved_count = _save_results(results) if save_to_db else 0
    csv_path = _export_csv(results, params) if export_csv else None
    return {
        "params": params,
        "event_count": len(events),
        "skipped_count": skipped_count,
        "result_count": len(results),
        "saved_count": saved_count,
        "csv_path": csv_path,
        "results": results,
        "summary": summarize_results(results),
    }
