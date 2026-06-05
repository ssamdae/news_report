from typing import Any

import pandas as pd

from database.db import get_connection


NEWS_COLUMNS = [
    "stock_code",
    "stock_name",
    "title",
    "link",
    "published_at",
    "source",
    "keyword",
]


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records_from_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    missing_columns = set(NEWS_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(
            "Missing required news columns: " + ", ".join(sorted(missing_columns))
        )

    records = df[NEWS_COLUMNS].to_dict("records")
    return [
        {key: _clean_value(value) for key, value in record.items()}
        for record in records
    ]


def save_news_articles(df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    rows = _records_from_dataframe(df)
    if not rows:
        return 0

    sql = """
        INSERT INTO news_article (
            stock_code,
            stock_name,
            title,
            link,
            published_at,
            source,
            keyword
        )
        VALUES (
            %(stock_code)s,
            %(stock_name)s,
            %(title)s,
            %(link)s,
            %(published_at)s,
            %(source)s,
            %(keyword)s
        )
        ON CONFLICT (link) DO NOTHING
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, rows)
        connection.commit()

    return len(rows)
