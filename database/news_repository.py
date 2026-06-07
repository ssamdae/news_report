import json
import os
import urllib.error
import urllib.request
from datetime import date
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
    "search_query",
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

ANALYSIS_COLUMNS = [
    "summary",
    "key_issues",
    "positive_points",
    "risk_points",
    "theme_points",
    "tomorrow_checkpoints",
    "sentiment",
    "confidence_score",
]


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

    if "search_query" in df.columns:
        df["relevance_reason"] = [
            (
                f"{reason}, search_query:{query}"
                if query and not pd.isna(query)
                else reason
            )
            for reason, query in zip(df["relevance_reason"], df["search_query"])
        ]

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
            search_query,
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
            %(search_query)s,
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
            keyword,
            search_query
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
                if row[7]:
                    score["relevance_reason"] = (
                        f"{score['relevance_reason']}, search_query:{row[7]}"
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


def get_relevant_news_for_analysis(
    stock_name: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            title,
            description,
            link,
            published_at,
            search_term,
            search_query,
            relevance_score
        FROM news_article
        WHERE stock_name = %(stock_name)s
            AND is_relevant = TRUE
        ORDER BY relevance_score DESC NULLS LAST,
            published_at DESC NULLS LAST,
            id DESC
        LIMIT %(limit)s
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_name": stock_name, "limit": limit})
            rows = cursor.fetchall()

    return [
        {
            "title": row[0],
            "description": row[1],
            "link": row[2],
            "published_at": row[3],
            "search_term": row[4],
            "search_query": row[5],
            "relevance_score": row[6],
        }
        for row in rows
    ]


def build_stock_analysis_prompt(
    stock_name: str,
    news_items: list[dict[str, Any]],
) -> str:
    news_lines = []
    for index, item in enumerate(news_items, start=1):
        published_at = item.get("published_at") or "-"
        title = item.get("title") or ""
        description = item.get("description") or ""
        search_query = item.get("search_query") or item.get("search_term") or "-"
        relevance_score = item.get("relevance_score")
        news_lines.append(
            "\n".join(
                [
                    f"{index}. 제목: {title}",
                    f"   설명: {description}",
                    f"   발행일: {published_at}",
                    f"   검색쿼리: {search_query}",
                    f"   관련성점수: {relevance_score}",
                ]
            )
        )

    news_text = "\n\n".join(news_lines) or "관련 뉴스 없음"
    return f"""
아래 뉴스는 {stock_name} 종목과 관련성이 있다고 필터링된 뉴스입니다.
투자 추천이 아니라 뉴스 기반 분석으로만 작성하세요.

분석 항목:
- 한줄 요약
- 핵심 이슈
- 상승/관심 요인
- 리스크 요인
- 관련 테마
- 내일 체크포인트
- 종합 분위기(sentiment): positive / neutral / negative 중 하나
- 신뢰도 점수(confidence_score): 0~100

반드시 아래 JSON 형식으로만 답하세요.
{{
  "summary": "...",
  "key_issues": "...",
  "positive_points": "...",
  "risk_points": "...",
  "theme_points": "...",
  "tomorrow_checkpoints": "...",
  "sentiment": "positive|neutral|negative",
  "confidence_score": 0
}}

뉴스 목록:
{news_text}
""".strip()


def build_mock_stock_analysis(
    stock_name: str,
    news_items: list[dict[str, Any]],
) -> dict[str, Any]:
    titles = [item.get("title") or "" for item in news_items if item.get("title")]
    top_titles = titles[:5]
    issue_text = "\n".join(f"- {title}" for title in top_titles) or "- 관련 뉴스 없음"
    query_terms = sorted(
        {
            str(item.get("search_term")).strip()
            for item in news_items
            if item.get("search_term")
        }
    )
    theme_text = ", ".join(query_terms[:8]) if query_terms else "관련 검색어 없음"
    source_count = len(news_items)
    confidence_score = min(80, 40 + source_count * 2)

    return {
        "summary": f"{stock_name} 관련 뉴스 {source_count}건을 기준으로 주요 이슈를 점검했습니다.",
        "key_issues": issue_text,
        "positive_points": "관련 뉴스 제목에서 확인되는 관심 요인을 중심으로 후속 보도가 이어지는지 확인이 필요합니다.",
        "risk_points": "뉴스 기반 임시 분석이므로 실제 실적, 수급, 공시와 함께 교차 확인해야 합니다.",
        "theme_points": theme_text,
        "tomorrow_checkpoints": "장 시작 전 추가 공시, 주요 고객사/테마 뉴스, 거래대금 변화를 확인하세요.",
        "sentiment": "neutral",
        "confidence_score": confidence_score,
    }


def call_stock_analysis_llm(prompt: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Use --mock to run without LLM.")

    request_body = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {
                "role": "system",
                "content": "You produce concise Korean stock news analysis as JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise RuntimeError(f"OpenAI API request failed: {error}") from error

    content = payload["choices"][0]["message"]["content"]
    return json.loads(content)


def normalize_stock_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    normalized = {column: analysis.get(column) for column in ANALYSIS_COLUMNS}
    sentiment = (normalized.get("sentiment") or "neutral").strip().lower()
    if sentiment not in {"positive", "neutral", "negative"}:
        sentiment = "neutral"
    normalized["sentiment"] = sentiment

    try:
        confidence_score = float(normalized.get("confidence_score") or 0)
    except (TypeError, ValueError):
        confidence_score = 0
    normalized["confidence_score"] = max(0, min(100, confidence_score))
    return normalized


def save_stock_analysis(
    stock_name: str,
    report_date: date,
    analysis: dict[str, Any],
    source_news_count: int,
) -> None:
    normalized = normalize_stock_analysis(analysis)
    sql = """
        INSERT INTO stock_analysis (
            stock_name,
            report_date,
            analysis_date,
            summary,
            key_issues,
            positive_points,
            risk_points,
            theme_points,
            tomorrow_checkpoints,
            sentiment,
            confidence_score,
            source_news_count,
            updated_at
        )
        VALUES (
            %(stock_name)s,
            %(report_date)s,
            NOW(),
            %(summary)s,
            %(key_issues)s,
            %(positive_points)s,
            %(risk_points)s,
            %(theme_points)s,
            %(tomorrow_checkpoints)s,
            %(sentiment)s,
            %(confidence_score)s,
            %(source_news_count)s,
            NOW()
        )
        ON CONFLICT (stock_name, report_date) DO UPDATE
        SET
            analysis_date = NOW(),
            summary = EXCLUDED.summary,
            key_issues = EXCLUDED.key_issues,
            positive_points = EXCLUDED.positive_points,
            risk_points = EXCLUDED.risk_points,
            theme_points = EXCLUDED.theme_points,
            tomorrow_checkpoints = EXCLUDED.tomorrow_checkpoints,
            sentiment = EXCLUDED.sentiment,
            confidence_score = EXCLUDED.confidence_score,
            source_news_count = EXCLUDED.source_news_count,
            updated_at = NOW()
    """
    params = {
        "stock_name": stock_name,
        "report_date": report_date,
        "source_news_count": source_news_count,
        **normalized,
    }

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
        connection.commit()


def analyze_stock_news(
    stock_name: str,
    report_date: date,
    limit: int = 20,
    mock: bool = False,
) -> dict[str, Any]:
    news_items = get_relevant_news_for_analysis(stock_name=stock_name, limit=limit)
    prompt = build_stock_analysis_prompt(stock_name, news_items)
    analysis = (
        build_mock_stock_analysis(stock_name, news_items)
        if mock
        else call_stock_analysis_llm(prompt)
    )
    normalized = normalize_stock_analysis(analysis)
    save_stock_analysis(
        stock_name=stock_name,
        report_date=report_date,
        analysis=normalized,
        source_news_count=len(news_items),
    )

    return {
        "stock_name": stock_name,
        "report_date": report_date,
        "source_news_count": len(news_items),
        **normalized,
    }


def get_stock_analysis(
    stock_name: str,
    report_date: date | None = None,
) -> pd.DataFrame:
    if report_date is None:
        sql = """
            SELECT
                stock_name,
                report_date,
                analysis_date,
                summary,
                key_issues,
                positive_points,
                risk_points,
                theme_points,
                tomorrow_checkpoints,
                sentiment,
                confidence_score,
                source_news_count
            FROM stock_analysis
            WHERE stock_name = %(stock_name)s
            ORDER BY report_date DESC, analysis_date DESC
            LIMIT 1
        """
        params = {"stock_name": stock_name}
    else:
        sql = """
            SELECT
                stock_name,
                report_date,
                analysis_date,
                summary,
                key_issues,
                positive_points,
                risk_points,
                theme_points,
                tomorrow_checkpoints,
                sentiment,
                confidence_score,
                source_news_count
            FROM stock_analysis
            WHERE stock_name = %(stock_name)s
                AND report_date = %(report_date)s
            ORDER BY analysis_date DESC
            LIMIT 1
        """
        params = {"stock_name": stock_name, "report_date": report_date}

    with get_connection() as connection:
        return pd.read_sql_query(sql, connection, params=params)


def get_relevant_news_for_display(
    stock_name: str,
    limit: int = 30,
) -> pd.DataFrame:
    sql = """
        SELECT
            title,
            search_query,
            relevance_score,
            published_at,
            link
        FROM news_article
        WHERE stock_name = %(stock_name)s
            AND is_relevant = TRUE
        ORDER BY relevance_score DESC NULLS LAST,
            published_at DESC NULLS LAST,
            id DESC
        LIMIT %(limit)s
    """

    with get_connection() as connection:
        return pd.read_sql_query(
            sql,
            connection,
            params={"stock_name": stock_name, "limit": limit},
        )
