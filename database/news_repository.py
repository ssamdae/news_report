from typing import Any

import pandas as pd

from database.db import get_connection


NEWS_COLUMNS = [
    "stock_code",
    "stock_name",
    "title",
    "description",
    "link",
    "published_at",
    "source",
    "keyword",
    "search_term",
    "search_term_type",
    "search_term_score",
]

KEYWORD_COLUMNS = [
    "stock_code",
    "keyword",
]


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records_from_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    required_columns = {
        "stock_code",
        "stock_name",
        "title",
        "link",
        "published_at",
        "source",
        "keyword",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            "Missing required news columns: " + ", ".join(sorted(missing_columns))
        )

    df = df.copy()
    for column in NEWS_COLUMNS:
        if column not in df.columns:
            df[column] = None

    records = df[NEWS_COLUMNS].to_dict("records")
    return [
        {key: _clean_value(value) for key, value in record.items()}
        for record in records
    ]


def load_active_stock_keywords(stock_codes: list[str]) -> pd.DataFrame:
    stock_codes = sorted(
        {str(stock_code).strip() for stock_code in stock_codes if stock_code}
    )
    if not stock_codes:
        return pd.DataFrame(columns=KEYWORD_COLUMNS)

    sql = """
        SELECT
            stock_code,
            keyword
        FROM stock_keyword_map
        WHERE is_active = TRUE
            AND stock_code = ANY(%(stock_codes)s)
        ORDER BY stock_code, keyword
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.stock_keyword_map')")
            if cursor.fetchone()[0] is None:
                return pd.DataFrame(columns=KEYWORD_COLUMNS)

        return pd.read_sql_query(
            sql,
            connection,
            params={"stock_codes": stock_codes},
        )


def load_stock_for_news(
    stock_code: str | None = None,
    stock_name: str | None = None,
) -> dict[str, Any] | None:
    stock_code = (stock_code or "").strip()
    stock_name = (stock_name or "").strip()

    if stock_code:
        sql = """
            SELECT
                stock_code,
                stock_name
            FROM stock_master
            WHERE stock_code = %(stock_code)s
            LIMIT 1
        """
        params = {"stock_code": stock_code}
    elif stock_name:
        sql = """
            SELECT
                m.stock_code,
                m.stock_name
            FROM stock_master m
            WHERE m.stock_name = %(stock_name)s
            UNION ALL
            SELECT
                NULL AS stock_code,
                p.stock_name
            FROM stock_profile p
            WHERE p.stock_name = %(stock_name)s
                AND NOT EXISTS (
                    SELECT 1
                    FROM stock_master m
                    WHERE m.stock_name = %(stock_name)s
                )
            LIMIT 1
        """
        params = {"stock_name": stock_name}
    else:
        return None

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "stock_code": row[0],
        "stock_name": row[1],
    }


def load_stock_search_terms(stock_name: str, limit: int) -> pd.DataFrame:
    sql = """
        SELECT
            search_term,
            term_type,
            score
        FROM stock_search_term
        WHERE stock_name = %(stock_name)s
        ORDER BY score DESC, search_term
        LIMIT %(limit)s
    """

    with get_connection() as connection:
        return pd.read_sql_query(
            sql,
            connection,
            params={"stock_name": stock_name, "limit": limit},
        )


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
            description,
            link,
            published_at,
            source,
            keyword,
            search_term,
            search_term_type,
            search_term_score
        )
        VALUES (
            %(stock_code)s,
            %(stock_name)s,
            %(title)s,
            %(description)s,
            %(link)s,
            %(published_at)s,
            %(source)s,
            %(keyword)s,
            %(search_term)s,
            %(search_term_type)s,
            %(search_term_score)s
        )
        ON CONFLICT (link) DO NOTHING
        RETURNING id
    """

    inserted_count = 0
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(sql, row)
                if cursor.fetchone() is not None:
                    inserted_count += 1
        connection.commit()

    return inserted_count
