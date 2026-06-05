from datetime import date, datetime, timedelta

import pandas as pd
from pykrx import stock


MARKETS = ("KOSPI", "KOSDAQ")
OUTPUT_COLUMNS = [
    "trade_date",
    "market",
    "stock_code",
    "stock_name",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "prev_close_price",
    "volume",
    "trading_value",
]


def _normalize_date(target_date: str | date) -> str:
    if isinstance(target_date, date):
        return target_date.strftime("%Y%m%d")

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(target_date, fmt).strftime("%Y%m%d")
        except ValueError:
            continue

    raise ValueError(
        f"target_date must be a date, YYYY-MM-DD, or YYYYMMDD value: {target_date!r}"
    )


def _get_market_ohlcv(yyyymmdd: str, market: str) -> pd.DataFrame:
    try:
        return stock.get_market_ohlcv_by_ticker(yyyymmdd, market=market)
    except KeyError as exc:
        raise RuntimeError(
            "pykrx returned an unexpected KRX response format. "
            "Use pykrx==1.2.8 or later-compatible 1.x version."
        ) from exc


def _get_all_market_ohlcv(yyyymmdd: str) -> dict[str, pd.DataFrame]:
    return {market: _get_market_ohlcv(yyyymmdd, market) for market in MARKETS}


def _has_any_market_data(market_frames: dict[str, pd.DataFrame]) -> bool:
    return any(not frame.empty for frame in market_frames.values())


def _find_business_day(target_yyyymmdd: str, max_lookback_days: int = 10) -> str:
    target = datetime.strptime(target_yyyymmdd, "%Y%m%d").date()

    for offset in range(max_lookback_days + 1):
        lookup_date = (target - timedelta(days=offset)).strftime("%Y%m%d")
        if _has_any_market_data(_get_all_market_ohlcv(lookup_date)):
            return lookup_date

    raise ValueError(
        f"No KRX trading data found from {target_yyyymmdd} back "
        f"{max_lookback_days} days."
    )


def _find_previous_business_day(target_yyyymmdd: str) -> str:
    previous_calendar_day = (
        datetime.strptime(target_yyyymmdd, "%Y%m%d").date() - timedelta(days=1)
    ).strftime("%Y%m%d")
    return _find_business_day(previous_calendar_day)


def _rename_ohlcv_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.reset_index()
    ticker_column = "티커" if "티커" in renamed.columns else renamed.columns[0]

    renamed = renamed.rename(
        columns={
            ticker_column: "stock_code",
            "시가": "open_price",
            "고가": "high_price",
            "저가": "low_price",
            "종가": "close_price",
            "거래량": "volume",
            "거래대금": "trading_value",
        }
    )
    required_columns = {
        "stock_code",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "trading_value",
    }
    missing_columns = required_columns - set(renamed.columns)
    if missing_columns:
        raise RuntimeError(
            "pykrx OHLCV response is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    return renamed


def _build_empty_result() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def collect_daily_stocks(target_date: str | date) -> pd.DataFrame:
    yyyymmdd = _normalize_date(target_date)
    market_ohlcv = _get_all_market_ohlcv(yyyymmdd)

    if not _has_any_market_data(market_ohlcv):
        raise ValueError(
            f"No KRX trading data found for target_date={yyyymmdd}. "
            "The date may be a holiday, weekend, future date, or KRX returned no data."
        )

    previous_business_day = _find_previous_business_day(yyyymmdd)
    frames: list[pd.DataFrame] = []

    for market, ohlcv in market_ohlcv.items():
        if ohlcv.empty:
            continue

        previous_ohlcv = _get_market_ohlcv(previous_business_day, market=market)
        frame = _rename_ohlcv_columns(ohlcv)
        previous_close = _rename_ohlcv_columns(previous_ohlcv)[
            ["stock_code", "close_price"]
        ].rename(columns={"close_price": "prev_close_price"})

        frame = frame.merge(previous_close, on="stock_code", how="left")
        frame["stock_name"] = frame["stock_code"].apply(stock.get_market_ticker_name)
        frame["market"] = market
        frame["trade_date"] = datetime.strptime(yyyymmdd, "%Y%m%d").date()

        frames.append(frame[OUTPUT_COLUMNS])

    if not frames:
        return _build_empty_result()

    return pd.concat(frames, ignore_index=True)
