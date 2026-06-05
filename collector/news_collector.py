import html
import os
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import pandas as pd
import requests

from database.db import load_environment


NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
DEFAULT_DISPLAY = 5
DEFAULT_SORT = "date"
DEFAULT_SLEEP_SECONDS = 0.2

OUTPUT_COLUMNS = [
    "stock_code",
    "stock_name",
    "title",
    "link",
    "published_at",
    "source",
    "keyword",
    "collected_at",
]


def _get_naver_credentials() -> tuple[str, str]:
    load_environment()
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "NAVER_CLIENT_ID and NAVER_CLIENT_SECRET must be set in environment or .env"
        )

    return client_id, client_secret


def _build_headers() -> dict[str, str]:
    client_id, client_secret = _get_naver_credentials()
    return {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }


def _clean_text(value: str | None) -> str:
    return html.unescape(value or "").replace("<b>", "").replace("</b>", "").strip()


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _extract_source(item: dict[str, Any]) -> str:
    originallink = item.get("originallink") or ""
    link = item.get("link") or ""
    url = originallink or link
    if not url:
        return "NAVER"

    host = url.split("//", 1)[-1].split("/", 1)[0]
    return host.replace("www.", "") or "NAVER"


def search_news_by_keyword(
    keyword: str,
    stock_code: str | None = None,
    stock_name: str | None = None,
    display: int = DEFAULT_DISPLAY,
    sort: str = DEFAULT_SORT,
) -> pd.DataFrame:
    keyword = keyword.strip()
    if not keyword:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    try:
        response = requests.get(
            NAVER_NEWS_API_URL,
            headers=_build_headers(),
            params={"query": keyword, "display": display, "start": 1, "sort": sort},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Naver News API request failed for keyword={keyword}: {exc}") from exc

    items = response.json().get("items", [])
    collected_at = datetime.now()
    rows: list[dict[str, Any]] = []

    for item in items:
        title = _clean_text(item.get("title"))
        link = item.get("originallink") or item.get("link")
        if not title or not link:
            continue

        rows.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "title": title,
                "link": link,
                "published_at": _parse_published_at(item.get("pubDate")),
                "source": _extract_source(item),
                "keyword": keyword,
                "collected_at": collected_at,
            }
        )

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def collect_news_for_signals(
    signal_df: pd.DataFrame,
    keyword_df: pd.DataFrame | None = None,
    display: int = DEFAULT_DISPLAY,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
) -> pd.DataFrame:
    if signal_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    frames: list[pd.DataFrame] = []
    signal_rows = signal_df.drop_duplicates(subset=["stock_code"]).to_dict("records")
    keywords_by_stock = _build_keywords_by_stock(keyword_df)

    for row in signal_rows:
        stock_code = str(row.get("stock_code", "")).strip()
        stock_name = str(row.get("stock_name", "")).strip()
        keywords = _build_search_keywords(
            stock_code=stock_code,
            stock_name=stock_name,
            mapped_keywords=keywords_by_stock.get(stock_code, []),
        )

        for keyword in keywords:
            try:
                frame = search_news_by_keyword(
                    keyword=keyword,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    display=display,
                )
                if not frame.empty:
                    frames.append(frame)
            except RuntimeError as exc:
                print(
                    f"[WARN] News collection skipped for "
                    f"{stock_code} {stock_name} keyword={keyword}: {exc}"
                )

            time.sleep(sleep_seconds)

    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    return pd.concat(frames, ignore_index=True)


def _build_keywords_by_stock(keyword_df: pd.DataFrame | None) -> dict[str, list[str]]:
    if keyword_df is None or keyword_df.empty:
        return {}

    missing_columns = {"stock_code", "keyword"} - set(keyword_df.columns)
    if missing_columns:
        raise ValueError(
            "Missing required keyword columns: " + ", ".join(sorted(missing_columns))
        )

    keywords_by_stock: dict[str, list[str]] = {}
    for row in keyword_df[["stock_code", "keyword"]].to_dict("records"):
        stock_code = str(row.get("stock_code", "")).strip()
        keyword = str(row.get("keyword", "")).strip()
        if not stock_code or not keyword:
            continue
        keywords_by_stock.setdefault(stock_code, []).append(keyword)

    return keywords_by_stock


def _build_search_keywords(
    stock_code: str,
    stock_name: str,
    mapped_keywords: list[str],
) -> list[str]:
    keywords = [stock_name or stock_code, *mapped_keywords]
    unique_keywords: list[str] = []
    seen: set[str] = set()

    for keyword in keywords:
        normalized = keyword.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_keywords.append(normalized)

    return unique_keywords
