"""Scan August 2026 KOSPI/KOSDAQ base bars and enrich hits with D0 investor flow.

This is an isolated CSV experiment. It does not read or write the production DB.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import pandas as pd


START_DATE = "20260801"
END_DATE = "20260831"
LOOKBACK_START = "20260720"  # Includes the last July trading day for C(1).
DEFAULT_OUTPUT = Path("output/basebar_202608_test.csv")
MIN_TRADE_VALUE = 50_000_000_000  # KRX trading value is in KRW.
MARKETS = ("KOSPI", "KOSDAQ")
INVESTORS = {
    "개인": "individual",
    "외국인": "foreign",
    "기타외국인": "other_foreign",
    "기관합계": "institution",
    "기타법인": "other_corp",
    "금융투자": "financial_investment",
    "보험": "insurance",
    "투신": "investment_trust",
    "사모": "private_equity",
    "은행": "bank",
    "기타금융": "other_financial",
    "연기금": "pension",
}
FLOW_COLUMNS = [f"{name}_net" for name in INVESTORS.values()]
RATIO_COLUMNS = [f"{name}_net_ratio" for name in INVESTORS.values()]
OUTPUT_COLUMNS = [
    "stock_code", "stock_name", "market", "trade_date", "prev_close",
    "open", "high", "low", "close", "volume", "trade_value",
    "trade_value_100m", "high_vs_prev_close_pct", "high_vs_low_pct",
    "close_vs_open_pct", "investor_flow_status", *FLOW_COLUMNS, *RATIO_COLUMNS,
]


def scan_day(today: pd.DataFrame, previous: pd.DataFrame, trade_date: str, market: str) -> list[dict]:
    """Apply the four Kiwoom conditions to one market snapshot."""
    required = {"시가", "고가", "저가", "종가", "거래량", "거래대금"}
    if not required.issubset(today.columns) or "종가" not in previous.columns:
        raise ValueError(f"Missing OHLCV columns for {market} {trade_date}")
    current = today.copy()
    current.index = current.index.astype(str).str.zfill(6)
    prior = previous.copy()
    prior.index = prior.index.astype(str).str.zfill(6)
    current["prev_close"] = pd.to_numeric(prior["종가"], errors="coerce").reindex(current.index)
    for column in required:
        current[column] = pd.to_numeric(current[column], errors="coerce")

    hits = current.loc[
        (current["거래대금"] >= MIN_TRADE_VALUE)
        & (current["prev_close"] > 0)
        & (current["시가"] > 0)
        & (current["저가"] > 0)
        & (current["고가"] * 100 >= current["prev_close"] * 115)
        & (current["고가"] * 100 >= current["저가"] * 115)
        & (current["종가"] * 100 >= current["시가"] * 109)
    ]
    rows = []
    for ticker, bar in hits.iterrows():
        rows.append({
            "stock_code": ticker, "market": market, "trade_date": trade_date,
            "prev_close": int(bar["prev_close"]), "open": int(bar["시가"]),
            "high": int(bar["고가"]), "low": int(bar["저가"]),
            "close": int(bar["종가"]), "volume": int(bar["거래량"]),
            "trade_value": int(bar["거래대금"]),
            "trade_value_100m": round(bar["거래대금"] / 100_000_000, 2),
            "high_vs_prev_close_pct": round((bar["고가"] / bar["prev_close"] - 1) * 100, 2),
            "high_vs_low_pct": round((bar["고가"] / bar["저가"] - 1) * 100, 2),
            "close_vs_open_pct": round((bar["종가"] / bar["시가"] - 1) * 100, 2),
        })
    return rows


def investor_flow(stock, ticker: str, trade_date: str, trade_value: int) -> dict:
    """Return exact-day net KRW; keep unavailable values blank, never zero-fill."""
    result = {"investor_flow_status": "missing", **dict.fromkeys(FLOW_COLUMNS + RATIO_COLUMNS)}
    try:
        flow = stock.get_market_trading_value_by_investor(trade_date, trade_date, ticker)
        if flow is None or flow.empty or "순매수" not in flow.columns:
            return result
        flow.index = flow.index.astype(str).str.strip()
        if not {"개인", "기관합계", "기타법인"}.issubset(flow.index):
            return result
        if "외국인" not in flow.index and "외국인합계" not in flow.index:
            return result
        for label, name in INVESTORS.items():
            lookup = "외국인합계" if label == "외국인" and label not in flow.index else label
            if lookup not in flow.index:
                continue
            value = pd.to_numeric(flow.loc[lookup, "순매수"], errors="coerce")
            if pd.isna(value):
                continue
            result[f"{name}_net"] = int(value)
            result[f"{name}_net_ratio"] = round(int(value) / trade_value * 100, 4)
        result["investor_flow_status"] = "ok"
    except Exception as exc:
        result["investor_flow_status"] = "error"
        print(f"[WARN] investor flow {ticker} {trade_date}: {exc}")
    return result


def collect(stock, with_flow: bool = True, pause: float = 0.2) -> list[dict]:
    days = [day.strftime("%Y%m%d") for day in stock.get_previous_business_days(
        fromdate=LOOKBACK_START, todate=END_DATE
    )]
    days = sorted(set(days))
    if not days or not any(day < START_DATE for day in days):
        raise RuntimeError("No July reference session; cannot evaluate C(1) on the first August session")
    rows: list[dict] = []
    for market in MARKETS:
        previous = None
        previous_day = None
        scanned = 0
        for day in days:
            snapshot = stock.get_market_ohlcv_by_ticker(day, market=market, alternative=False)
            if snapshot is None or snapshot.empty:
                raise RuntimeError(f"Empty OHLCV for {market} {day}; scan is incomplete")
            if day >= START_DATE:
                if previous is None:
                    raise RuntimeError(f"Missing previous session for {market} {day}")
                print(f"[SCAN] {market} {day} (previous {previous_day})", flush=True)
                rows.extend(scan_day(snapshot, previous, day, market))
                scanned += 1
            previous, previous_day = snapshot, day
            if pause:
                time.sleep(pause)
        print(f"[INFO] {market}: {scanned} August sessions scanned", flush=True)
    if with_flow:
        for index, row in enumerate(rows, start=1):
            row.update(investor_flow(stock, row["stock_code"], row["trade_date"], row["trade_value"]))
            row["stock_name"] = stock.get_market_ticker_name(row["stock_code"])
            print(f"[FLOW] {index}/{len(rows)} {row['stock_code']} {row['investor_flow_status']}", flush=True)
            if pause:
                time.sleep(pause)
    else:
        for row in rows:
            row["stock_name"] = stock.get_market_ticker_name(row["stock_code"])
            row["investor_flow_status"] = "skipped"
    return sorted(rows, key=lambda row: (row["trade_date"], -row["trade_value"], row["stock_code"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-flow", action="store_true", help="Scan bars without investor requests")
    parser.add_argument("--pause", type=float, default=0.2, help="Seconds between API requests")
    args = parser.parse_args()
    if args.pause < 0:
        parser.error("--pause must be nonnegative")
    from pykrx import stock

    rows = collect(stock, with_flow=not args.no_flow, pause=args.pause)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    statuses = pd.Series([row["investor_flow_status"] for row in rows]).value_counts().to_dict()
    print(f"[DONE] {len(rows)} hits, flow={statuses}, output={args.output}")


if __name__ == "__main__":
    main()
