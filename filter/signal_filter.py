import pandas as pd


TRADING_VALUE_THRESHOLD = 50_000_000_000


REQUIRED_COLUMNS = {
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "prev_close_price",
    "trading_value",
}


def filter_500eok_signal(df: pd.DataFrame) -> pd.DataFrame:
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    valid_prices = (
        df["prev_close_price"].notna()
        & (df["prev_close_price"] > 0)
        & (df["low_price"] > 0)
        & (df["open_price"] > 0)
    )

    condition = (
        valid_prices
        & (df["trading_value"] >= TRADING_VALUE_THRESHOLD)
        & (df["high_price"] >= df["prev_close_price"] * 1.15)
        & (df["high_price"] >= df["low_price"] * 1.15)
        & (df["close_price"] >= df["open_price"] * 1.09)
    )

    return df.loc[condition].copy()
