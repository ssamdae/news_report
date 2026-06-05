import os
import time
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pandas as pd
import requests


NAVER_DAILY_URL = "https://finance.naver.com/item/sise_day.naver"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_CSV = PROJECT_ROOT / "data" / "stock_master.csv"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_SLEEP_SECONDS = 0.2
DEFAULT_MAX_PAGES = 30
MIN_SLEEP_SECONDS = 0.1
MAX_SLEEP_SECONDS = 0.3

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

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


class NaverDailyTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_td = False
        self._current_cell: list[str] = []
        self._current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "td":
            self._in_td = True
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "td" and self._in_td:
            value = "".join(self._current_cell).strip()
            self._current_row.append(value)
            self._in_td = False
            return

        if tag == "tr":
            cells = [cell for cell in self._current_row if cell]
            if len(cells) >= 7:
                self.rows.append(cells[:7])
            self._current_row = []


def _normalize_date(target_date: str | date) -> date:
    if isinstance(target_date, date):
        return target_date

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(target_date, fmt).date()
        except ValueError:
            continue

    raise ValueError(
        f"target_date must be a date, YYYY-MM-DD, or YYYYMMDD value: {target_date!r}"
    )


def _normalize_stock_code(stock_code: Any) -> str:
    value = str(stock_code).strip()
    if value.endswith(".0"):
        value = value[:-2]
    return value.zfill(6)


def _to_int(value: str) -> int:
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        raise ValueError("empty numeric value")
    return int(cleaned)


def calculate_trading_value(row: dict[str, Any]) -> int:
    return int(row["close_price"]) * int(row["volume"])


def _get_sleep_seconds() -> float:
    configured = float(os.getenv("NAVER_REQUEST_SLEEP_SECONDS", DEFAULT_SLEEP_SECONDS))
    return min(max(configured, MIN_SLEEP_SECONDS), MAX_SLEEP_SECONDS)


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )
    return session


def load_stock_master_from_csv(csv_path: str | os.PathLike[str] | None = None) -> pd.DataFrame:
    path = Path(csv_path or os.getenv("STOCK_MASTER_CSV", DEFAULT_MASTER_CSV))
    if not path.exists():
        raise FileNotFoundError(
            "Stock master CSV not found. Create a CSV with columns "
            f"stock_code, stock_name, market at {path}"
        )

    master = pd.read_csv(path, dtype={"stock_code": str})
    required_columns = {"stock_code", "stock_name", "market"}
    missing_columns = required_columns - set(master.columns)
    if missing_columns:
        raise ValueError(
            "Stock master CSV is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    master = master[["stock_code", "stock_name", "market"]].dropna().copy()
    master["stock_code"] = master["stock_code"].apply(_normalize_stock_code)
    master["stock_name"] = master["stock_name"].astype(str).str.strip()
    master["market"] = master["market"].astype(str).str.strip().str.upper()
    master = master.drop_duplicates(subset=["stock_code"])
    master = master[master["stock_code"].str.fullmatch(r"\d{6}")]

    if master.empty:
        raise ValueError("Stock master CSV has no valid stock rows.")

    return master.reset_index(drop=True)


def load_stock_master(csv_path: str | os.PathLike[str] | None = None) -> pd.DataFrame:
    return load_stock_master_from_csv(csv_path)


def refresh_stock_master() -> pd.DataFrame:
    raise NotImplementedError(
        "Automatic stock master refresh is not implemented yet. "
        "Provide data/stock_master.csv before running the collector."
    )


def _fetch_naver_daily_page(
    session: requests.Session,
    stock_code: str,
    page: int,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    try:
        response = session.get(
            NAVER_DAILY_URL,
            params={"code": stock_code, "page": page},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Naver Finance request failed for stock_code={stock_code}, page={page}: {exc}"
        ) from exc

    response.encoding = response.apparent_encoding or "euc-kr"
    return response.text


def _parse_naver_daily_rows(html: str, stock_code: str) -> list[dict[str, Any]]:
    parser = NaverDailyTableParser()
    parser.feed(html)

    rows: list[dict[str, Any]] = []
    for cells in parser.rows:
        try:
            trade_date = datetime.strptime(cells[0], "%Y.%m.%d").date()
            close_price = _to_int(cells[1])
            open_price = _to_int(cells[3])
            high_price = _to_int(cells[4])
            low_price = _to_int(cells[5])
            volume = _to_int(cells[6])
        except ValueError:
            continue

        rows.append(
            {
                "trade_date": trade_date,
                "stock_code": stock_code,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "close_price": close_price,
                "volume": volume,
            }
        )
        rows[-1]["trading_value"] = calculate_trading_value(rows[-1])

    return rows


def get_daily_stock_price(
    stock_code: str,
    stock_name: str,
    target_date: str | date,
    market: str = "",
    session: requests.Session | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> pd.DataFrame:
    normalized_date = _normalize_date(target_date)
    normalized_code = _normalize_stock_code(stock_code)
    own_session = session is None
    session = session or _build_session()
    collected_rows: list[dict[str, Any]] = []

    try:
        for page in range(1, max_pages + 1):
            html = _fetch_naver_daily_page(session, normalized_code, page)
            page_rows = _parse_naver_daily_rows(html, normalized_code)
            if not page_rows:
                raise ValueError(
                    f"Naver Finance returned no daily rows for stock_code={normalized_code}."
                )

            collected_rows.extend(page_rows)
            dates = [row["trade_date"] for row in collected_rows]

            if normalized_date in dates:
                target_index = dates.index(normalized_date)
                if target_index + 1 >= len(collected_rows):
                    continue

                row = collected_rows[target_index].copy()
                row["prev_close_price"] = collected_rows[target_index + 1]["close_price"]
                row["stock_name"] = stock_name
                row["market"] = market
                return pd.DataFrame([row], columns=OUTPUT_COLUMNS)

            if min(dates) < normalized_date:
                raise ValueError(
                    f"No Naver daily data for stock_code={normalized_code}, "
                    f"target_date={normalized_date.isoformat()}. "
                    "The date may be a holiday, weekend, future date, or missing from Naver."
                )

        raise ValueError(
            f"Could not find target_date={normalized_date.isoformat()} and previous "
            f"close for stock_code={normalized_code} within {max_pages} Naver pages."
        )
    finally:
        if own_session:
            session.close()


def collect_daily_stocks(target_date: str | date) -> pd.DataFrame:
    normalized_date = _normalize_date(target_date)
    master = load_stock_master()
    sleep_seconds = _get_sleep_seconds()
    session = _build_session()
    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    try:
        for row in master.to_dict("records"):
            stock_code = _normalize_stock_code(row["stock_code"])
            stock_name = str(row["stock_name"])
            market = str(row["market"])

            try:
                frames.append(
                    get_daily_stock_price(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        target_date=normalized_date,
                        market=market,
                        session=session,
                    )
                )
            except (RuntimeError, ValueError) as exc:
                message = f"{stock_code} {stock_name}: {exc}"
                print(f"[WARN] {message}")
                errors.append(message)

            time.sleep(sleep_seconds)
    finally:
        session.close()

    if not frames:
        print(
            f"[WARN] No stock data collected for target_date={normalized_date.isoformat()}. "
            "Returning an empty DataFrame."
        )
        for message in errors[:5]:
            print(f"[WARN] sample error: {message}")
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    return pd.concat(frames, ignore_index=True)
