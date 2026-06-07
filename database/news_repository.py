from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd

from database.db import get_connection, load_environment


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

REQUIRED_ANALYSIS_FIELDS = set(ANALYSIS_COLUMNS)

DAILY_THEME_ANALYSIS_COLUMNS = [
    "market_summary",
    "strong_themes",
    "theme_rankings",
    "key_issues",
    "market_drivers",
    "leading_stocks",
    "top_picks",
    "risk_points",
    "tomorrow_checkpoints",
    "confidence_score",
]

REQUIRED_DAILY_THEME_ANALYSIS_FIELDS = set(DAILY_THEME_ANALYSIS_COLUMNS)


class StockAnalysisLlmError(RuntimeError):
    def __init__(self, message: str, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value)


def _to_decimal_score(value: Any, default: int | float | str = 0) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(str(default))


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
    cleaned_records = [
        {key: _clean_value(value) for key, value in record.items()}
        for record in records
    ]

    for record in cleaned_records:
        if record.get("relevance_score") is None:
            record["relevance_score"] = 0
        if record.get("relevance_reason") is None:
            record["relevance_reason"] = "not_scored"
        if record.get("is_relevant") is None:
            record["is_relevant"] = False

    return cleaned_records


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


def load_news_for_summary(
    report_date: date,
    stock_name: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stock_filter = "AND stock_name = %(stock_name)s" if stock_name else ""
    sql = f"""
        SELECT
            id,
            stock_name,
            title,
            description,
            search_term,
            search_query,
            source,
            published_at,
            relevance_score
        FROM news_article
        WHERE is_relevant = TRUE
            AND (ai_summary IS NULL OR TRIM(ai_summary) = '')
            AND (
                published_at::date = %(report_date)s
                OR created_at::date = %(report_date)s
            )
            {stock_filter}
        ORDER BY relevance_score DESC NULLS LAST,
            published_at DESC NULLS LAST,
            id DESC
        LIMIT %(limit)s
    """
    params: dict[str, Any] = {"report_date": report_date, "limit": limit}
    if stock_name:
        params["stock_name"] = stock_name

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return _rows_to_dicts(cursor)


def build_news_summary_prompt(news_item: dict[str, Any]) -> str:
    return f"""
아래 뉴스 정보를 바탕으로 한국어 1~2문장 요약을 작성하세요.
투자자가 3초 안에 이해할 수 있도록 80자 이내로 요약하세요.
줄바꿈을 넣지 말고 한 줄로 작성하세요.
투자 추천이나 가격 전망은 하지 말고, 뉴스에서 확인되는 사실과 의미만 간결하게 요약하세요.

반드시 아래 JSON 형식으로만 답하세요.
{{
  "summary": "..."
}}

종목: {_to_text(news_item.get("stock_name"))}
제목: {_to_text(news_item.get("title"))}
설명: {_to_text(news_item.get("description"))}
검색어: {_to_text(news_item.get("search_term") or news_item.get("search_query"))}
출처: {_to_text(news_item.get("source"))}
발행시각: {_to_text(news_item.get("published_at"))}
""".strip()


def build_mock_news_summary(news_item: dict[str, Any]) -> str:
    title = _to_text(news_item.get("title"))
    description = _to_text(news_item.get("description"))
    stock_name = _to_text(news_item.get("stock_name"))
    if description:
        return f"{stock_name} 관련 뉴스로, {title} 이슈가 보도됐습니다. {description[:120]}"
    return f"{stock_name} 관련 뉴스로, {title} 이슈가 확인됐습니다."


def run_llm_news_summary(news_item: dict[str, Any]) -> str:
    result = _run_openai_json_prompt(
        build_news_summary_prompt(news_item),
        {"summary"},
        error_context="뉴스 요약",
    )
    return _to_text(result.get("summary"))


def update_news_ai_summary(article_id: int, ai_summary: str) -> None:
    sql = """
        UPDATE news_article
        SET ai_summary = %(ai_summary)s
        WHERE id = %(id)s
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"id": article_id, "ai_summary": ai_summary})
        connection.commit()


def summarize_news_articles(
    report_date: date,
    stock_name: str | None = None,
    limit: int = 100,
    mock: bool = False,
) -> dict[str, Any]:
    news_items = load_news_for_summary(
        report_date=report_date,
        stock_name=stock_name,
        limit=limit,
    )
    success_count = 0
    errors: list[dict[str, str]] = []

    for item in news_items:
        try:
            summary = (
                build_mock_news_summary(item)
                if mock
                else run_llm_news_summary(item)
            )
            update_news_ai_summary(int(item["id"]), summary)
            success_count += 1
        except Exception as error:
            errors.append(
                {
                    "id": str(item.get("id")),
                    "title": _to_text(item.get("title"))[:80],
                    "error": str(error),
                }
            )

    return {
        "report_date": report_date,
        "target_count": len(news_items),
        "success_count": success_count,
        "error_count": len(errors),
        "errors": errors,
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
매수, 매도, 보유 같은 투자 행동을 권하지 마세요.
뉴스로 확인되지 않은 내용은 단정하지 말고 불확실하다고 표현하세요.
과도한 확신이나 가격 전망을 피하고, 관찰 가능한 이슈와 체크포인트 중심으로 작성하세요.

분석 항목:
- 한줄 요약
- 핵심 이슈
- 상승/관심 요인
- 리스크 요인
- 관련 테마
- 내일 체크포인트
- 종합 분위기(sentiment): positive / neutral / negative 중 하나
- 신뢰도 점수(confidence_score): 0~100, 뉴스 수와 구체성에 따라 보수적으로 산정

반드시 아래 JSON 형식으로만 답하세요. JSON 앞뒤에 설명, 마크다운, 코드블록을 붙이지 마세요.
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


def _run_openai_json_prompt(
    prompt: str,
    required_fields: set[str],
    *,
    error_context: str,
) -> dict[str, Any]:
    load_environment()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise StockAnalysisLlmError(
            "OPENAI_API_KEY가 설정되어 있지 않습니다. "
            ".env에 OPENAI_API_KEY를 설정하거나 --mock 옵션을 사용하세요."
        )

    request_body = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You produce concise Korean stock news analysis as strict JSON. "
                    "Do not provide investment recommendations."
                ),
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
            response_text = response.read().decode("utf-8")
            payload = json.loads(response_text)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise StockAnalysisLlmError(
            f"{error_context} OpenAI API 요청 실패: HTTP {error.code}",
            raw_response=error_body,
        ) from error
    except urllib.error.URLError as error:
        raise StockAnalysisLlmError(
            f"{error_context} OpenAI API 요청 실패: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise StockAnalysisLlmError(
            f"{error_context} OpenAI API 응답 JSON 파싱에 실패했습니다.",
            raw_response=locals().get("response_text", ""),
        ) from error

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise StockAnalysisLlmError(
            f"{error_context} OpenAI API 응답 구조가 예상과 다릅니다.",
            raw_response=json.dumps(payload, ensure_ascii=False)[:1000],
        ) from error

    try:
        analysis = json.loads(content)
    except json.JSONDecodeError as error:
        raise StockAnalysisLlmError(
            f"{error_context} LLM 분석 결과 JSON 파싱에 실패했습니다.",
            raw_response=content,
        ) from error

    if not isinstance(analysis, dict):
        raise StockAnalysisLlmError(
            f"{error_context} LLM 분석 결과가 JSON object가 아닙니다.",
            raw_response=content,
        )

    missing_fields = required_fields - set(analysis)
    if missing_fields:
        raise StockAnalysisLlmError(
            f"{error_context} LLM 분석 결과에 필수 필드가 없습니다: "
            + ", ".join(sorted(missing_fields)),
            raw_response=content,
        )

    return analysis


def run_llm_stock_analysis(prompt: str) -> dict[str, Any]:
    return _run_openai_json_prompt(
        prompt,
        REQUIRED_ANALYSIS_FIELDS,
        error_context="종목 분석",
    )


def call_stock_analysis_llm(prompt: str) -> dict[str, Any]:
    return run_llm_stock_analysis(prompt)


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


def load_signal_stock_names_for_analysis(report_date: date) -> list[str]:
    sql = """
        SELECT DISTINCT
            m.stock_name
        FROM signal_event e
        JOIN stock_master m
            ON m.stock_code = e.stock_code
        WHERE e.signal_date = %(report_date)s
            AND e.signal_name = '500억봉'
        ORDER BY m.stock_name
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            rows = cursor.fetchall()

    return [row[0] for row in rows if row[0]]


def analyze_signal_stocks(
    report_date: date,
    limit: int = 20,
    mock: bool = False,
) -> dict[str, Any]:
    stock_names = load_signal_stock_names_for_analysis(report_date)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for stock_name in stock_names:
        try:
            result = analyze_stock_news(
                stock_name=stock_name,
                report_date=report_date,
                limit=limit,
                mock=mock,
            )
        except Exception as error:
            errors.append({"stock_name": stock_name, "error": str(error)})
            continue

        results.append(result)

    return {
        "report_date": report_date,
        "target_count": len(stock_names),
        "success_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
    }


def analyze_signal_event_stocks(
    report_date: date,
    limit_news: int = 20,
    mock: bool = False,
) -> dict[str, Any]:
    signal_stocks = get_signal_stocks_by_date(report_date)
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for stock in signal_stocks:
        stock_name = stock.get("stock_name")
        if not stock_name:
            skipped.append(
                {
                    "stock_name": stock.get("stock_code") or "-",
                    "reason": "종목명 없음",
                }
            )
            continue

        news_items = get_relevant_news_for_analysis(
            stock_name=stock_name,
            limit=limit_news,
        )
        if not news_items and not mock:
            print(f"{stock_name}: 관련 뉴스 부족")
            skipped.append({"stock_name": stock_name, "reason": "관련 뉴스 부족"})
            continue

        if not news_items:
            print(f"{stock_name}: 관련 뉴스 부족 - mock 분석 생성")

        try:
            result = analyze_stock_news(
                stock_name=stock_name,
                report_date=report_date,
                limit=limit_news,
                mock=mock,
            )
        except Exception as error:
            errors.append({"stock_name": stock_name, "error": str(error)})
            continue

        results.append(result)

    return {
        "report_date": report_date,
        "target_count": len(signal_stocks),
        "success_count": len(results),
        "skip_count": len(skipped),
        "error_count": len(errors),
        "results": results,
        "skipped": skipped,
        "errors": errors,
    }


def get_signal_stocks_by_date(report_date: date) -> list[dict[str, Any]]:
    sql = """
        SELECT
            se.stock_code,
            sm.stock_name,
            se.signal_date AS report_date,
            se.signal_name,
            se.trading_value,
            se.close_price,
            se.volume
        FROM signal_event se
        JOIN stock_master sm
            ON se.stock_code = sm.stock_code
        WHERE se.signal_date = %(report_date)s
        ORDER BY se.trading_value DESC NULLS LAST, sm.stock_name
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            return _rows_to_dicts(cursor)


def _load_stock_profiles(stock_names: list[str]) -> dict[str, dict[str, Any]]:
    if not stock_names:
        return {}

    sql = """
        SELECT
            stock_name,
            primary_theme,
            secondary_theme,
            related_themes,
            theme_count,
            total_hit_count
        FROM stock_profile
        WHERE stock_name = ANY(%(stock_names)s)
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_names": stock_names})
            rows = _rows_to_dicts(cursor)

    return {row["stock_name"]: row for row in rows}


def _load_stock_terms(stock_names: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not stock_names:
        return {}

    sql = """
        SELECT
            stock_name,
            search_term,
            term_type,
            score
        FROM stock_search_term
        WHERE stock_name = ANY(%(stock_names)s)
            AND term_type IN ('PRIMARY_THEME', 'SECONDARY_THEME', 'KEYWORD')
        ORDER BY stock_name, score DESC, search_term
    """

    terms_by_stock: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_names": stock_names})
            for row in _rows_to_dicts(cursor):
                if len(terms_by_stock[row["stock_name"]]) < 10:
                    terms_by_stock[row["stock_name"]].append(row)

    return dict(terms_by_stock)


def _load_stock_analyses(
    stock_names: list[str],
    report_date: date,
) -> dict[str, dict[str, Any]]:
    if not stock_names:
        return {}

    sql = """
        SELECT
            stock_name,
            summary,
            key_issues,
            positive_points,
            risk_points,
            theme_points,
            sentiment,
            confidence_score,
            source_news_count
        FROM stock_analysis
        WHERE report_date = %(report_date)s
            AND stock_name = ANY(%(stock_names)s)
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {"stock_names": stock_names, "report_date": report_date},
            )
            rows = _rows_to_dicts(cursor)

    return {row["stock_name"]: row for row in rows}


def _load_relevant_news_by_stock(
    stock_names: list[str],
    limit_per_stock: int,
) -> dict[str, list[dict[str, Any]]]:
    if not stock_names:
        return {}

    sql = """
        WITH ranked_news AS (
            SELECT
                stock_name,
                title,
                source,
                search_term,
                search_query,
                relevance_score,
                published_at,
                ROW_NUMBER() OVER (
                    PARTITION BY stock_name
                    ORDER BY relevance_score DESC NULLS LAST,
                        published_at DESC NULLS LAST,
                        id DESC
                ) AS row_number
            FROM news_article
            WHERE stock_name = ANY(%(stock_names)s)
                AND is_relevant = TRUE
        )
        SELECT
            stock_name,
            title,
            source,
            search_term,
            search_query,
            relevance_score,
            published_at
        FROM ranked_news
        WHERE row_number <= %(limit_per_stock)s
        ORDER BY stock_name, relevance_score DESC NULLS LAST,
            published_at DESC NULLS LAST
    """

    news_by_stock: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {
                    "stock_names": stock_names,
                    "limit_per_stock": max(1, limit_per_stock),
                },
            )
            for row in _rows_to_dicts(cursor):
                news_by_stock[row["stock_name"]].append(row)

    return dict(news_by_stock)


def _load_stock_knowledge_context(stock_names: list[str]) -> list[dict[str, Any]]:
    if not stock_names:
        return []

    sql = """
        SELECT
            stock_name,
            node_type,
            node_value,
            relation_type,
            source,
            score
        FROM stock_knowledge_graph
        WHERE stock_name = ANY(%(stock_names)s)
        ORDER BY score DESC, stock_name, node_type
        LIMIT 80
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_names": stock_names})
            return _rows_to_dicts(cursor)


def _load_stock_theme_history_context(stock_names: list[str]) -> list[dict[str, Any]]:
    if not stock_names:
        return []

    sql = """
        SELECT
            m.stock_name,
            t.theme_name,
            m.hit_count,
            m.avg_change_rate,
            m.max_change_rate,
            m.total_trading_value,
            m.first_seen_date,
            m.last_seen_date
        FROM stock_theme_map m
        JOIN theme_master t
            ON t.id = m.theme_id
        WHERE m.stock_name = ANY(%(stock_names)s)
        ORDER BY m.hit_count DESC, m.total_trading_value DESC NULLS LAST
        LIMIT 80
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_names": stock_names})
            return _rows_to_dicts(cursor)


def _load_canonical_theme_context() -> list[dict[str, Any]]:
    sql = """
        SELECT
            canonical_name,
            category_name,
            description,
            priority
        FROM canonical_theme_master
        WHERE is_active = TRUE
        ORDER BY priority, canonical_name
        LIMIT 40
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return _rows_to_dicts(cursor)


def _load_pdf_signal_history_context(
    stock_names: list[str],
    report_date: date,
) -> list[dict[str, Any]]:
    if not stock_names:
        return []

    sql = """
        SELECT
            report_date,
            theme_name,
            stock_name,
            change_rate,
            trading_value
        FROM pdf_signal_item
        WHERE stock_name = ANY(%(stock_names)s)
            AND (report_date IS NULL OR report_date <= %(report_date)s)
        ORDER BY report_date DESC NULLS LAST,
            trading_value DESC NULLS LAST,
            change_rate DESC NULLS LAST
        LIMIT 80
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {"stock_names": stock_names, "report_date": report_date},
            )
            return _rows_to_dicts(cursor)


def _choose_stock_theme(
    stock_name: str,
    profile: dict[str, Any] | None,
    terms: list[dict[str, Any]],
) -> str:
    if profile and profile.get("primary_theme"):
        return str(profile["primary_theme"]).strip()

    for term_type in ("PRIMARY_THEME", "SECONDARY_THEME", "KEYWORD"):
        for term in terms:
            if term.get("term_type") == term_type and term.get("search_term"):
                return str(term["search_term"]).strip()

    return stock_name or "개별주"


def _build_daily_theme_groups(
    signal_stocks: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    terms_by_stock: dict[str, list[dict[str, Any]]],
    analyses: dict[str, dict[str, Any]],
    news_by_stock: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for stock in signal_stocks:
        stock_name = stock["stock_name"]
        terms = terms_by_stock.get(stock_name, [])
        profile = profiles.get(stock_name)
        analysis = analyses.get(stock_name, {})
        news_items = news_by_stock.get(stock_name, [])
        theme = _choose_stock_theme(stock_name, profile, terms)

        group = grouped.setdefault(
            theme,
            {
                "theme": theme,
                "stocks": [],
                "keyword_counter": Counter(),
                "sentiment_counter": Counter(),
                "news_count": 0,
                "top_news": [],
            },
        )

        group["stocks"].append(
            {
                "stock_code": stock.get("stock_code"),
                "stock_name": stock_name,
                "market": stock.get("market"),
                "trading_value": _safe_float(stock.get("trading_value")),
                "close_price": _safe_float(stock.get("close_price")),
                "volume": stock.get("volume"),
                "summary": analysis.get("summary"),
                "key_issues": analysis.get("key_issues"),
                "positive_points": analysis.get("positive_points"),
                "risk_points": analysis.get("risk_points"),
                "theme_points": analysis.get("theme_points"),
                "sentiment": analysis.get("sentiment"),
                "confidence_score": _safe_float(analysis.get("confidence_score")),
            }
        )

        for term in terms:
            keyword = str(term.get("search_term") or "").strip()
            if keyword:
                group["keyword_counter"][keyword] += 1

        sentiment = (analysis.get("sentiment") or "unknown").strip()
        group["sentiment_counter"][sentiment] += 1
        group["news_count"] += len(news_items)
        group["top_news"].extend(
            {
                "stock_name": stock_name,
                "title": item.get("title"),
                "search_query": item.get("search_query") or item.get("search_term"),
                "relevance_score": _safe_float(item.get("relevance_score")),
            }
            for item in news_items
            if item.get("title")
        )

    theme_groups = []
    for group in grouped.values():
        stocks = sorted(
            group["stocks"],
            key=lambda row: row.get("trading_value") or 0,
            reverse=True,
        )
        top_news = sorted(
            group["top_news"],
            key=lambda row: row.get("relevance_score") or 0,
            reverse=True,
        )
        theme_groups.append(
            {
                "theme": group["theme"],
                "stock_count": len(stocks),
                "leading_stocks": stocks[:8],
                "keywords": [
                    keyword for keyword, _count in group["keyword_counter"].most_common(10)
                ],
                "sentiment_distribution": dict(group["sentiment_counter"]),
                "news_count": group["news_count"],
                "top_news": top_news[:10],
            }
        )

    return sorted(
        theme_groups,
        key=lambda row: (row["stock_count"], row["news_count"]),
        reverse=True,
    )


def load_daily_theme_source_data(
    report_date: date,
    limit_news_per_stock: int = 5,
) -> dict[str, Any]:
    signal_stocks = get_signal_stocks_by_date(report_date)
    stock_names = [row["stock_name"] for row in signal_stocks if row.get("stock_name")]
    profiles = _load_stock_profiles(stock_names)
    terms_by_stock = _load_stock_terms(stock_names)
    analyses = _load_stock_analyses(stock_names, report_date)
    news_by_stock = _load_relevant_news_by_stock(stock_names, limit_news_per_stock)
    market_context = {
        "stock_knowledge_graph": _load_stock_knowledge_context(stock_names),
        "stock_theme_map_history": _load_stock_theme_history_context(stock_names),
        "canonical_themes": _load_canonical_theme_context(),
        "pdf_signal_history": _load_pdf_signal_history_context(
            stock_names,
            report_date,
        ),
    }
    theme_groups = _build_daily_theme_groups(
        signal_stocks=signal_stocks,
        profiles=profiles,
        terms_by_stock=terms_by_stock,
        analyses=analyses,
        news_by_stock=news_by_stock,
    )

    return {
        "report_date": report_date,
        "signal_stocks": signal_stocks,
        "theme_groups": theme_groups,
        "market_context": market_context,
        "source_stock_count": len(signal_stocks),
        "source_news_count": sum(len(items) for items in news_by_stock.values()),
    }


def build_daily_theme_analysis_prompt(
    report_date: date,
    grouped_theme_data: list[dict[str, Any]],
    market_context: dict[str, Any] | None = None,
) -> str:
    theme_data_text = json.dumps(
        grouped_theme_data[:15],
        ensure_ascii=False,
        default=str,
        indent=2,
    )
    context_text = json.dumps(
        market_context or {},
        ensure_ascii=False,
        default=str,
        indent=2,
    )
    return f"""
아래 데이터는 {report_date.isoformat()} 당일 500억봉 종목을 테마별로 묶은 자료입니다.
뉴스, 종목별 AI 분석, 검색 키워드, 대표 테마, 지식 그래프, 과거 강세 사례를 근거로 당일 시장을 분석하세요.

분석 기준:
- 투자 추천, 매수/매도/보유 의견을 제시하지 마세요.
- 뉴스/테마/500억봉/지식 그래프/과거 강세 사례 데이터 기반으로만 분석하세요.
- 테마를 나열하지 말고 왜 시장이 해당 테마를 선택했는지 원인과 자금 흐름 중심으로 설명하세요.
- 증권사 데일리 시황 코멘트 스타일로 작성하세요.
- market_summary는 "오늘 시장 한줄 요약" 성격으로 500자~1000자 수준의 완성된 문단으로 작성하세요.
- strong_themes는 "자금이 몰린 섹터/테마"를 자금 흐름과 연결해 설명하세요.
- market_drivers는 "시장이 기대하는 핵심 모멘텀"을 정책, 산업, 글로벌 기업, 수급, 실적 기대감 중심으로 작성하세요.
- tomorrow_checkpoints는 "내일 관전 포인트"로 작성하세요.
- top_picks는 "주도주 선정 배경" 관점으로 TOP PICK 3와 이유를 작성하세요.
- 불확실한 내용은 단정하지 말고 불확실하다고 표현하세요.
- 과도한 가격 전망이나 수익률 전망을 피하세요.
- mock, 테스트, 샘플, 임시 분석이라는 표현을 절대 쓰지 마세요.
- 기존 저장값을 설명하지 말고 새 분석 결과만 작성하세요.
- top_picks는 당일 500억봉 종목 중 주목도 높은 3개와 선정 이유를 작성하세요.
- top_picks 선정에는 거래대금, 관련 뉴스 수, relevance_score, 테마 대표성, 종목별 sentiment/confidence를 함께 참고하세요.
- market_drivers는 개별 종목보다 상위 이슈 중심으로 작성하세요.
- market_drivers에는 정책, 산업, 글로벌 기업, 수급, 실적 기대감 등 시장을 움직인 핵심 요인을 요약하세요.

반드시 아래 JSON 형식으로만 답하세요. JSON 앞뒤에 설명, 마크다운, 코드블록을 붙이지 마세요.
confidence_score를 제외한 모든 필드는 배열이나 객체가 아니라 문자열로 반환하세요.
confidence_score는 반드시 0 이상 100 이하의 숫자로 반환하세요. 문자열, null, 빈 값, 설명 문장은 허용하지 않습니다.
theme_rankings도 배열이 아니라 "1위 반도체: ...\n2위 AI/로봇: ..." 형태의 문자열이어야 합니다.
{{
  "market_summary": "...",
  "strong_themes": "...",
  "theme_rankings": "1위 반도체: ...\n2위 AI/로봇: ...",
  "key_issues": "...",
  "market_drivers": "...",
  "leading_stocks": "...",
  "top_picks": "1. 종목명: 선정 이유...\n2. 종목명: 선정 이유...\n3. 종목명: 선정 이유...",
  "risk_points": "...",
  "tomorrow_checkpoints": "...",
  "confidence_score": 70
}}

테마별 집계 데이터:
{theme_data_text}

추가 시장 컨텍스트:
{context_text}
""".strip()


def build_mock_daily_theme_analysis(
    report_date: date,
    theme_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    top_groups = theme_groups[:5]
    theme_names = [group["theme"] for group in top_groups]
    total_stocks = sum(group["stock_count"] for group in theme_groups)
    total_news = sum(group["news_count"] for group in theme_groups)

    rankings = "\n".join(
        (
            f"{index}. {group['theme']} "
            f"(종목 {group['stock_count']}개, 뉴스 {group['news_count']}건, "
            f"키워드: {', '.join(group['keywords'][:5]) or '-'})"
        )
        for index, group in enumerate(top_groups, start=1)
    ) or "- 집계된 테마 없음"
    leading_stocks = "\n".join(
        (
            f"- {group['theme']}: "
            + ", ".join(
                stock["stock_name"] for stock in group["leading_stocks"][:5]
            )
        )
        for group in top_groups
    ) or "- 집계된 종목 없음"
    key_issues = "\n".join(
        (
            f"- {group['theme']}: "
            + "; ".join(news["title"] for news in group["top_news"][:3])
        )
        for group in top_groups
        if group["top_news"]
    ) or "- 관련 뉴스 부족"
    top_picks = "\n".join(
        (
            f"{index}. {stock['stock_name']}: "
            f"{group['theme']} 대표 흐름, 거래대금 "
            f"{stock.get('trading_value') or 0:,.0f}, "
            f"관련 뉴스 {group['news_count']}건 기준으로 관찰 대상입니다."
        )
        for index, (group, stock) in enumerate(
            [
                (group, stock)
                for group in top_groups
                for stock in group["leading_stocks"][:1]
            ][:3],
            start=1,
        )
    ) or "- 선정 대상 부족"
    market_drivers = "\n".join(
        f"- {group['theme']}: {', '.join(group['keywords'][:5]) or '키워드 부족'}"
        for group in top_groups
    ) or "- 집계된 시장 핵심 이슈 없음"

    confidence_score = min(85, 35 + len(theme_groups) * 3 + total_news)

    return {
        "market_summary": (
            f"{report_date.isoformat()} 500억봉 종목 {total_stocks}개를 기준으로 "
            f"{', '.join(theme_names) or '주요 테마'} 흐름이 관찰됐습니다."
        ),
        "strong_themes": ", ".join(theme_names) or "집계된 테마 없음",
        "theme_rankings": rankings,
        "key_issues": key_issues,
        "market_drivers": market_drivers,
        "leading_stocks": leading_stocks,
        "top_picks": top_picks,
        "risk_points": "mock 분석이므로 실제 뉴스 본문, 공시, 수급 데이터와 함께 추가 확인이 필요합니다.",
        "tomorrow_checkpoints": "상위 테마의 후속 뉴스, 거래대금 지속 여부, 관련 종목 확산 여부를 확인하세요.",
        "confidence_score": confidence_score,
    }


def run_llm_daily_theme_analysis(prompt: str) -> dict[str, Any]:
    return _run_openai_json_prompt(
        prompt,
        REQUIRED_DAILY_THEME_ANALYSIS_FIELDS,
        error_context="일간 테마 분석",
    )


def normalize_daily_theme_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        column: analysis.get(column) for column in DAILY_THEME_ANALYSIS_COLUMNS
    }

    for column in DAILY_THEME_ANALYSIS_COLUMNS:
        if column != "confidence_score":
            normalized[column] = _to_text(normalized.get(column))

    if "mock 분석이므로" in normalized["risk_points"]:
        normalized["risk_points"] = normalized["risk_points"].replace(
            "mock 분석이므로 ",
            "",
        )
    for column in DAILY_THEME_ANALYSIS_COLUMNS:
        if column != "confidence_score":
            normalized[column] = normalized[column].replace("mock 분석", "분석")

    confidence_score = _to_decimal_score(normalized.get("confidence_score"))
    confidence_score = max(Decimal("0"), min(Decimal("100"), confidence_score))
    normalized["confidence_score"] = confidence_score
    return normalized


def _default_daily_theme_confidence(
    source_stock_count: int,
    source_news_count: int,
) -> Decimal:
    if source_stock_count > 0 and source_news_count > 0:
        return Decimal("70")
    if source_stock_count > 0:
        return Decimal("50")
    return Decimal("30")


def save_daily_theme_analysis(
    report_date: date,
    analysis: dict[str, Any],
    source_stock_count: int,
    source_news_count: int,
) -> dict[str, Any]:
    normalized = normalize_daily_theme_analysis(analysis)
    if normalized["confidence_score"] <= 0:
        normalized["confidence_score"] = _default_daily_theme_confidence(
            source_stock_count=source_stock_count,
            source_news_count=source_news_count,
        )
        print(f"confidence_score 보정 적용: {normalized['confidence_score']}")

    sql = """
        INSERT INTO daily_theme_analysis (
            report_date,
            market_summary,
            strong_themes,
            theme_rankings,
            key_issues,
            market_drivers,
            leading_stocks,
            top_picks,
            risk_points,
            tomorrow_checkpoints,
            confidence_score,
            source_stock_count,
            source_news_count,
            updated_at
        )
        VALUES (
            %(report_date)s,
            %(market_summary)s,
            %(strong_themes)s,
            %(theme_rankings)s,
            %(key_issues)s,
            %(market_drivers)s,
            %(leading_stocks)s,
            %(top_picks)s,
            %(risk_points)s,
            %(tomorrow_checkpoints)s,
            %(confidence_score)s,
            %(source_stock_count)s,
            %(source_news_count)s,
            NOW()
        )
        ON CONFLICT (report_date) DO UPDATE
        SET
            market_summary = EXCLUDED.market_summary,
            strong_themes = EXCLUDED.strong_themes,
            theme_rankings = EXCLUDED.theme_rankings,
            key_issues = EXCLUDED.key_issues,
            market_drivers = EXCLUDED.market_drivers,
            leading_stocks = EXCLUDED.leading_stocks,
            top_picks = EXCLUDED.top_picks,
            risk_points = EXCLUDED.risk_points,
            tomorrow_checkpoints = EXCLUDED.tomorrow_checkpoints,
            confidence_score = EXCLUDED.confidence_score,
            source_stock_count = EXCLUDED.source_stock_count,
            source_news_count = EXCLUDED.source_news_count,
            updated_at = NOW()
    """
    params = {
        "report_date": report_date,
        "source_stock_count": source_stock_count,
        "source_news_count": source_news_count,
        **normalized,
    }

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
        connection.commit()

    return normalized


def analyze_daily_themes(
    report_date: date,
    limit_news_per_stock: int = 5,
    mock: bool = False,
) -> dict[str, Any]:
    source_data = load_daily_theme_source_data(
        report_date=report_date,
        limit_news_per_stock=limit_news_per_stock,
    )
    theme_groups = source_data["theme_groups"]
    prompt = build_daily_theme_analysis_prompt(
        report_date,
        theme_groups,
        market_context=source_data["market_context"],
    )
    analysis = (
        build_mock_daily_theme_analysis(report_date, theme_groups)
        if mock
        else run_llm_daily_theme_analysis(prompt)
    )
    normalized = save_daily_theme_analysis(
        report_date=report_date,
        analysis=analysis,
        source_stock_count=source_data["source_stock_count"],
        source_news_count=source_data["source_news_count"],
    )

    return {
        "report_date": report_date,
        "source_stock_count": source_data["source_stock_count"],
        "source_news_count": source_data["source_news_count"],
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


def get_stock_analysis_by_report_date(report_date: date) -> pd.DataFrame:
    sql = """
        SELECT
            a.stock_name,
            a.report_date,
            a.analysis_date,
            a.summary,
            a.sentiment,
            a.confidence_score,
            a.source_news_count
        FROM stock_analysis a
        WHERE a.report_date = %(report_date)s
        ORDER BY a.confidence_score DESC NULLS LAST, a.stock_name
    """

    with get_connection() as connection:
        return pd.read_sql_query(sql, connection, params={"report_date": report_date})


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
