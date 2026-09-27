"""Evaluate pullback -> base-close reclaim -> settlement for August 2026 bars.

Uses the independently scanned CSV, never the production signal_event table.
Outcomes without enough observed sessions remain pending rather than failed.
"""

from __future__ import annotations

import argparse
import csv
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo


DEFAULT_INPUT = Path("output/basebar_202608_test.csv")
DEFAULT_OUTPUT = Path("output/basebar_202608_reclaim.csv")
RESULT_COLUMNS = [
    "stock_code", "stock_name", "market", "signal_date", "base_close",
    "observed_through", "observed_days", "horizon_days", "status",
    "first_pullback_date", "days_to_pullback", "pullback_low_pct",
    "reclaim_date", "days_to_reclaim", "settlement_above_days",
    "settlement_observed_days", "settled_above_base_close",
]


def evaluate_event(event: dict, history: list[dict], horizon: int) -> dict:
    """A strict close-below pullback, later close-above reclaim, then 2/3 closes.

    The breakout day does not count among the three settlement sessions.
    Days are observed ticker trading sessions, indexed from D+1.
    """
    signal = event["trade_date"]
    base_close = int(event["close"])
    result = {
        "stock_code": event["stock_code"], "stock_name": event["stock_name"],
        "market": event["market"], "signal_date": signal,
        "base_close": base_close, "observed_through": "", "observed_days": 0,
        "horizon_days": horizon, "status": "no_pullback_yet",
        "first_pullback_date": "", "days_to_pullback": "", "pullback_low_pct": "",
        "reclaim_date": "", "days_to_reclaim": "", "settlement_above_days": "",
        "settlement_observed_days": "", "settled_above_base_close": "",
    }
    by_date = {bar["date"]: bar for bar in history}
    if signal not in by_date or int(by_date[signal]["close"]) != base_close:
        result["status"] = "base_close_mismatch"
        return result
    future = [bar for day, bar in sorted(by_date.items()) if day > signal]
    window = future[:horizon]
    result["observed_days"] = len(window)
    if future:
        result["observed_through"] = future[-1]["date"]
    pullback_idx = next((i for i, bar in enumerate(window) if int(bar["close"]) < base_close), None)
    if pullback_idx is None:
        if len(window) >= horizon:
            result["status"] = "no_pullback_within_horizon"
        return result
    result["first_pullback_date"] = future[pullback_idx]["date"]
    result["days_to_pullback"] = pullback_idx + 1
    result["status"] = "no_reclaim_yet"
    reclaim_idx = next(
        (i for i in range(pullback_idx + 1, len(window)) if int(window[i]["close"]) > base_close),
        None,
    )
    trough_end = reclaim_idx if reclaim_idx is not None else len(window)
    result["pullback_low_pct"] = round(
        (min(int(bar["low"]) for bar in window[:trough_end]) / base_close - 1) * 100, 2
    )
    if reclaim_idx is None:
        if len(window) >= horizon:
            result["status"] = "no_reclaim_within_horizon"
        return result
    result["reclaim_date"] = future[reclaim_idx]["date"]
    result["days_to_reclaim"] = reclaim_idx + 1
    settlement = future[reclaim_idx + 1 : reclaim_idx + 4]
    result["settlement_observed_days"] = len(settlement)
    result["settlement_above_days"] = sum(int(bar["close"]) > base_close for bar in settlement)
    if len(settlement) < 3:
        result["status"] = "awaiting_settlement"
        return result
    success = result["settlement_above_days"] >= 2
    result["settled_above_base_close"] = success
    result["status"] = "settled" if success else "failed_first_reclaim"
    return result


def load_events(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        events = list(csv.DictReader(handle))
    if not events:
        raise ValueError(f"No base bars in {path}")
    required = {"stock_code", "stock_name", "market", "trade_date", "close"}
    if not required.issubset(events[0]):
        raise ValueError(f"Missing columns: {sorted(required - set(events[0]))}")
    if any(not ("20260801" <= row["trade_date"] <= "20260831") for row in events):
        raise ValueError("Input contains events outside August 2026")
    if len({(r["stock_code"], r["trade_date"]) for r in events}) != len(events):
        raise ValueError("Duplicate ticker/date events in input")
    return events


def collect_history_pykrx(stock, ticker: str, first_date: str, through: str) -> list[dict]:
    frame = stock.get_market_ohlcv_by_date(first_date, through, ticker, adjusted=False)
    if frame is None or frame.empty or not {"종가", "저가"}.issubset(frame.columns):
        return []
    return [
        {"date": day.strftime("%Y%m%d"), "close": int(bar["종가"]), "low": int(bar["저가"])}
        for day, bar in frame.iterrows() if int(bar["종가"]) > 0 and int(bar["저가"]) > 0
    ]


def collect_history_naver(session, ticker: str, first_date: str, through: str) -> list[dict]:
    """Read the Naver chart XML endpoint, with enough rows to include D0."""
    start = datetime.strptime(first_date, "%Y%m%d").date()
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    count = min(6000, max(100, (today - start).days + 30))
    response = session.get(
        "https://fchart.stock.naver.com/sise.nhn",
        params={"symbol": ticker, "timeframe": "day", "count": count, "requestType": "0"},
        timeout=20,
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content.decode("euc-kr"))
    by_date = {}
    for item in root.iter("item"):
        parts = (item.get("data") or "").split("|")
        if len(parts) != 6:
            raise RuntimeError(f"Unexpected Naver price row for {ticker}")
        day, _, _, low, close, _ = parts
        if first_date <= day <= through:
            by_date[day] = {"date": day, "close": int(close), "low": int(low)}
    if first_date not in by_date:
        raise RuntimeError(f"Naver chart history missing base date {first_date} for {ticker}")
    return [by_date[day] for day in sorted(by_date)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--through", default=datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"))
    parser.add_argument("--horizon", type=int, default=60)
    parser.add_argument("--provider", choices=("naver", "pykrx"), default="naver")
    parser.add_argument("--pause", type=float, default=0.2)
    args = parser.parse_args()
    try:
        datetime.strptime(args.through, "%Y%m%d")
    except ValueError:
        parser.error("--through must be YYYYMMDD")
    if args.horizon < 4:
        parser.error("--horizon must be at least 4 sessions")
    if args.pause < 0:
        parser.error("--pause must be nonnegative")
    if args.through < "20260801":
        parser.error("--through must not precede August 2026")

    events = load_events(args.input)
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_ticker[event["stock_code"]].append(event)
    results = []
    if args.provider == "pykrx":
        from pykrx import stock
        session = None
    else:
        import requests
        stock = None
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/xml,text/xml,*/*"})
    try:
        for i, (ticker, group) in enumerate(sorted(by_ticker.items()), start=1):
            first_date = min(row["trade_date"] for row in group)
            if args.provider == "naver":
                history = collect_history_naver(session, ticker, first_date, args.through)
            else:
                history = collect_history_pykrx(stock, ticker, first_date, args.through)
            if not history:
                raise RuntimeError(f"No price history for {ticker}; refusing incomplete output")
            for event in group:
                results.append(evaluate_event(event, history, args.horizon))
            print(f"[PRICE] {i}/{len(by_ticker)} {ticker}: {len(group)} events", flush=True)
            if args.pause:
                time.sleep(args.pause)
    finally:
        if session is not None:
            session.close()
    results.sort(key=lambda row: (row["signal_date"], row["stock_code"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)
    status_counts = defaultdict(int)
    for result in results:
        status_counts[result["status"]] += 1
    print(f"[DONE] {len(results)} events, status={dict(status_counts)}, output={args.output}")


if __name__ == "__main__":
    main()
