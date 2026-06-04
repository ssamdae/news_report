from datetime import date, datetime, timedelta

import pandas as pd
from pykrx import stock


MARKETS = ("KOSPI", "KOSDAQ")


def _normalize_date(target_date: str | date) -> str:
    if isinstance(target_date, date):
        return target_date.strftime("%Y%m%d")

    return datetime.strptime(target_date, "%Y-%m-%d").strftime("%Y%m%d")


def collect_daily_stocks(target_date: str | date) -> pd.DataFrame:
    yyyymmdd = _normalize_date(target_date)
    previous_lookup_date = _normalize_date(
        datetime.strptime(yyyymmdd, "%Y%m%d").date() - timedelta(days=1)
    )
    previous_business_day = stock.get_nearest_business_day_in_a_week(previous_lookup_date)
    frames: list[pd.DataFrame] = []

    for market in MARKETS:
        ohlcv = stock.get_market_ohlcv_by_ticker(yyyymmdd, market=market)
        if ohlcv.empty:
            continue
        previous_ohlcv = stock.get_market_ohlcv_by_ticker(
            previous_business_day,
            market=market,
        )

        frame = ohlcv.reset_index().rename(
            columns={
                "티커": "stock_code",
                "시가": "open_price",
                "고가": "high_price",
                "저가": "low_price",
                "종가": "close_price",
                "거래량": "volume",
                "거래대금": "trading_value",
            }
        )
        previous_close = previous_ohlcv[["종가"]].reset_index().rename(
            columns={"티커": "stock_code", "종가": "prev_close_price"}
        )
        frame = frame.merge(previous_close, on="stock_code", how="left")
        frame["stock_name"] = frame["stock_code"].apply(stock.get_market_ticker_name)
        frame["market"] = market
        frame["trade_date"] = datetime.strptime(yyyymmdd, "%Y%m%d").date()

        frames.append(
            frame[
                [
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
            ]
        )

    if not frames:
        return pd.DataFrame(
            columns=[
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
        )

    return pd.concat(frames, ignore_index=True)
