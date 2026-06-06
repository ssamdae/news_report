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
    "relevance_score",
    "relevance_reason",
    "is_relevant",
]

KEYWORD_COLUMNS = [
    "stock_code",
    "keyword",
]

BROAD_SEARCH_TERMS = {
    "반도체",
    "바이오",
    "이차전지",
    "전력",
    "에너지",
    "AI",
    "엔비디아",
}

TERM_TYPE_WEIGHTS = {
    "STOCK_NAME": 30,
    "PRIMARY_THEME": 10,
    "KEYWORD": 20,
    "SECONDARY_THEME": 5,
    "RELATED_THEME": 0,
}


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def calculate_news_relevance(
    stock_name: str | None,
    title: str | None,
    description: str | None,
    search_term: str | None,
    search_term_type: str | None,
) -> dict[str, Any]:
    stock_name = (stock_name or "").strip()
    title = title or ""
    description = description or ""
    search_term = (search_term or "").strip()
    search_term_type = (search_term_type or "").strip()

    score = 0
    reasons: list[str] = []

    stock_in_title = bool(stock_name and stock_name in title)
    stock_in_description = bool(stock_name and stock_name in description)
    term_in_title = bool(search_term and search_term in title)
    term_in_description = bool(search_term and search_term in description)

    if stock_in_title:
        score += 60
        reasons.append("title_stock_name:+60")
    if stock_in_description:
        score += 40
        reasons.append("description_stock_name:+40")
    if term_in_title:
        score += 20
        reasons.append("title_search_term:+20")
    if term_in_description:
        score += 10
        reasons.append("description_search_term:+10")

    type_weight = TERM_TYPE_WEIGHTS.get(search_term_type, 0)
    if type_weight:
        score += type_weight
        reasons.append(f"term_type_{search_term_type}:+{type_weight}")

    stock_mentioned = stock_in_title or stock_in_description
    if search_term_type in {"PRIMARY_THEME", "RELATED_THEME"} and not stock_mentioned:
        if score > 40:
            reasons.append("theme_without_stock_cap:40")
        score = min(score, 40)

    if search_term in BROAD_SEARCH_TERMS and not stock_mentioned:
        if score > 35:
            reasons.append("broad_term_without_stock_cap:35")
        score = min(score, 35)

    return {
        "relevance_score": score,
        "relevance_reason": ", ".join(reasons) or "no_match",
        "is_relevant": score >= 50,
    }


def apply_news_relevance_scores(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    scores = [
        calculate_news_relevance(
            stock_name=row.get("stock_name"),
            title=row.get("title"),
            description=row.get("description"),
            search_term=row.get("search_term") or row.get("keyword"),
            search_term_type=row.get("search_term_type"),
        )
        for row in df.to_dict("records")
    ]

    df["relevance_score"] = [score["relevance_score"] for score in scores]
    df["relevance_reason"] = [score["relevance_reason"] for score in scores]
    df["is_relevant"] = [score["is_relevant"] for score in scores]
    return df


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
            search_term_score,
            relevance_score,
            relevance_reason,
            is_relevant
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
            %(search_term_score)s,
            %(relevance_score)s,
            %(relevance_reason)s,
            %(is_relevant)s
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


def score_news_relevance(stock_name: str, limit: int | None = None) -> dict[str, Any]:
    limit_clause = "LIMIT %(limit)s" if limit is not None else ""
    select_sql = f"""
        SELECT
            id,
            stock_name,
            title,
            description,
            search_term,
            search_term_type,
            keyword
        FROM news_article
        WHERE stock_name = %(stock_name)s
        ORDER BY published_at DESC NULLS LAST, id DESC
        {limit_clause}
    """
    update_sql = """
        UPDATE news_article
        SET
            relevance_score = %(relevance_score)s,
            relevance_reason = %(relevance_reason)s,
            is_relevant = %(is_relevant)s
        WHERE id = %(id)s
    """

    updated_count = 0
    relevant_count = 0
    irrelevant_count = 0
    score_sum = 0

    params: dict[str, Any] = {"stock_name": stock_name}
    if limit is not None:
        params["limit"] = limit

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(select_sql, params)
            rows = cursor.fetchall()

            for row in rows:
                article_id = row[0]
                score = calculate_news_relevance(
                    stock_name=row[1],
                    title=row[2],
                    description=row[3],
                    search_term=row[4] or row[6],
                    search_term_type=row[5],
                )
                cursor.execute(update_sql, {"id": article_id, **score})

                updated_count += 1
                score_sum += score["relevance_score"]
                if score["is_relevant"]:
                    relevant_count += 1
                else:
                    irrelevant_count += 1

        connection.commit()

    average_score = score_sum / updated_count if updated_count else 0
    return {
        "updated_count": updated_count,
        "relevant_count": relevant_count,
        "irrelevant_count": irrelevant_count,
        "average_relevance_score": average_score,
    }
