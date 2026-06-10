from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any

from database.db import get_connection


STOP_TERMS = {
    "주식",
    "증시",
    "코스피",
    "코스닥",
    "상승",
    "하락",
    "급등",
    "급락",
    "개별주",
    "테마주",
    "관련주",
    "수혜주",
    "대장주",
}

PRIORITY_SUBTHEME_KEYWORDS = {
    "HBM",
    "AI반도체",
    "반도체장비",
    "반도체 장비",
    "후공정",
    "전공정",
    "유리기판",
    "전력반도체",
    "SOCAMM",
    "CXL",
    "온디바이스AI",
    "데이터센터",
    "휴머노이드",
    "산업용로봇",
    "스마트팩토리",
    "로봇",
    "ADC",
    "기술수출",
    "비만치료제",
    "제약바이오",
    "원전",
    "방산",
    "우주항공",
    "조선",
    "이차전지",
    "ESS",
    "전고체",
    "전해액",
    "리튬",
    "전선",
    "전력기기",
    "전력망",
}

KEYWORD_ALIASES = {
    "반도체 장비": "반도체장비",
    "AI 반도체": "AI반도체",
    "에이아이반도체": "AI반도체",
    "온디바이스 AI": "온디바이스AI",
    "제약 바이오": "제약바이오",
    "2차전지": "이차전지",
    "2차 전지": "이차전지",
    "우주 항공": "우주항공",
}

GENERIC_SUBTHEME_STOPWORDS = {
    "반도체",
    "바이오",
    "AI",
    "삼성",
    "LG",
    "SK",
    "현대",
    "개별주",
    "BIO",
    "디플",
    "반디플",
    "관련주",
    "수혜주",
    "테마주",
    "급등",
    "상승",
    "종목",
    "기업",
    "실적",
    "매출",
    "주가",
    "증시",
    "시장",
    "공시",
    "뉴스",
}

EXTRA_STOP_TERMS = {
    "관련주",
    "수혜주",
    "테마주",
    "급등",
    "상승",
    "종목",
    "기업",
    "실적",
    "매출",
    "주식",
    "증시",
    "시장",
    "뉴스",
    "공시",
    "대장주",
}


def _rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_keyword(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" -_/·,()[]{}")
    return KEYWORD_ALIASES.get(text, text)


def _priority_keywords() -> set[str]:
    return {_normalize_keyword(keyword) for keyword in PRIORITY_SUBTHEME_KEYWORDS}


def _is_priority_keyword(keyword: str) -> bool:
    return _normalize_keyword(keyword) in _priority_keywords()


def _contains_stopword(keyword: str) -> bool:
    normalized = _normalize_keyword(keyword)
    compact = re.sub(r"[\s#_/·,+&()\\[\\]{}-]+", "", normalized)
    for stopword in STOP_TERMS | EXTRA_STOP_TERMS | GENERIC_SUBTHEME_STOPWORDS:
        normalized_stopword = _normalize_keyword(stopword)
        compact_stopword = re.sub(
            r"[\s#_/·,+&()\\[\\]{}-]+",
            "",
            normalized_stopword,
        )
        if normalized_stopword and normalized_stopword in normalized:
            return True
        if compact_stopword and compact_stopword in compact:
            return True
    return False


def _is_noise_keyword(keyword: str, stock_names: set[str]) -> bool:
    normalized = _normalize_keyword(keyword)
    if not normalized:
        return True
    if _is_priority_keyword(normalized):
        return False
    if _contains_stopword(normalized):
        return True
    if normalized in stock_names:
        return True
    if len(normalized) < 2 and not normalized.isupper():
        return True
    if normalized.isdigit():
        return True
    return False


def _is_ascii_only(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9]+", value))


def _split_profile_terms(value: Any) -> list[str]:
    text = str(value or "")
    if not text.strip():
        return []
    return [
        _normalize_keyword(term)
        for term in re.split(r"\s*,\s*|/|·|\+|&", text)
        if _normalize_keyword(term)
    ]


def _stock_sort_key(row: dict[str, Any]) -> tuple[float, float]:
    investment_score = _safe_float(row.get("investment_score"))
    confidence_score = _safe_float(row.get("confidence_score")) or 0
    return (
        investment_score if investment_score is not None else -1,
        confidence_score,
    )


def _load_signal_stock_rows(report_date: date) -> list[dict[str, Any]]:
    sql = """
        WITH latest_analysis AS (
            SELECT DISTINCT ON (stock_name)
                stock_name,
                investment_score,
                investment_grade,
                confidence_score,
                analysis_date,
                id
            FROM stock_analysis
            WHERE analysis_date::date = %(report_date)s
            ORDER BY stock_name, analysis_date DESC, id DESC
        )
        SELECT
            se.stock_code,
            sm.stock_name,
            COALESCE(sp.primary_theme, '') AS primary_theme,
            COALESCE(sp.secondary_theme, '') AS secondary_theme,
            COALESCE(sp.related_themes, '') AS related_themes,
            se.trading_value,
            la.investment_score,
            la.investment_grade,
            la.confidence_score,
            sps.source_pdf_count
        FROM signal_event se
        JOIN stock_master sm
            ON sm.stock_code = se.stock_code
        LEFT JOIN stock_profile sp
            ON sp.stock_name = sm.stock_name
        LEFT JOIN latest_analysis la
            ON la.stock_name = sm.stock_name
        LEFT JOIN stock_pattern_stats sps
            ON sps.stock_name = sm.stock_name
        WHERE se.signal_date = %(report_date)s
        ORDER BY se.trading_value DESC NULLS LAST, sm.stock_name
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            return _rows_to_dicts(cursor)


def _load_knowledge_keywords(stock_names: list[str]) -> list[dict[str, Any]]:
    if not stock_names:
        return []
    sql = """
        SELECT
            stock_name,
            node_value,
            score
        FROM stock_knowledge_graph
        WHERE node_type = 'KEYWORD'
            AND stock_name = ANY(%(stock_names)s)
        ORDER BY stock_name, score DESC NULLS LAST, node_value
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_names": stock_names})
            return _rows_to_dicts(cursor)


def _load_pdf_theme_keywords(stock_names: list[str]) -> list[dict[str, Any]]:
    if not stock_names:
        return []
    sql = """
        SELECT
            stock_name,
            theme_name,
            COUNT(*)::integer AS pdf_count
        FROM pdf_signal_item
        WHERE stock_name = ANY(%(stock_names)s)
        GROUP BY stock_name, theme_name
        ORDER BY stock_name, pdf_count DESC, theme_name
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"stock_names": stock_names})
            return _rows_to_dicts(cursor)


def _load_news_subtheme_hits(
    stock_names: list[str],
    report_date: date,
) -> list[dict[str, Any]]:
    if not stock_names:
        return []
    sql = """
        SELECT
            stock_name,
            COALESCE(title, '') || ' ' ||
            COALESCE(description, '') || ' ' ||
            COALESCE(ai_summary, '') AS news_text
        FROM news_article
        WHERE stock_name = ANY(%(stock_names)s)
            AND (
                published_at::date = %(report_date)s
                OR created_at::date = %(report_date)s
            )
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                {"stock_names": stock_names, "report_date": report_date},
            )
            return _rows_to_dicts(cursor)


def _extract_priority_keywords_from_text(text: Any) -> list[str]:
    normalized_text = str(text or "").replace(" ", "")
    hits = []
    for keyword in sorted(_priority_keywords(), key=len, reverse=True):
        compact_keyword = keyword.replace(" ", "")
        if compact_keyword and compact_keyword in normalized_text:
            hits.append(keyword)
    return hits


def _add_candidate(
    grouped: dict[str, dict[str, Any]],
    keyword: str,
    stock: dict[str, Any],
    source: str,
    weight: float,
    pdf_count: int = 0,
    stock_names: set[str] | None = None,
) -> None:
    stock_names = stock_names or set()
    subtheme = _normalize_keyword(keyword)
    if _is_noise_keyword(subtheme, stock_names):
        return

    entry = grouped.setdefault(
        subtheme,
        {
            "subtheme": subtheme,
            "stocks_by_name": {},
            "pdf_count": 0,
            "source_weight": 0.0,
            "sources": set(),
        },
    )
    stock_name = stock["stock_name"]
    existing = entry["stocks_by_name"].get(stock_name)
    if existing is None or _stock_sort_key(stock) > _stock_sort_key(existing):
        entry["stocks_by_name"][stock_name] = stock
    entry["pdf_count"] += int(pdf_count or 0)
    entry["source_weight"] += weight
    entry["sources"].add(source)


def _allow_final_subtheme(
    subtheme: str,
    stocks: list[dict[str, Any]],
    pdf_count: int,
    stock_names: set[str],
) -> tuple[bool, bool]:
    normalized = _normalize_keyword(subtheme)
    if _is_noise_keyword(normalized, stock_names):
        return False, False
    if _is_priority_keyword(normalized):
        return True, False
    if len(normalized) <= 2:
        return False, False
    if _is_ascii_only(normalized):
        return False, False
    return pdf_count >= 3 and len(stocks) >= 2, True


def build_subtheme_rankings(
    report_date: date,
    include_debug: bool = False,
) -> list[dict[str, Any]]:
    signal_rows = _load_signal_stock_rows(report_date)
    if not signal_rows:
        return []

    stock_by_name = {row["stock_name"]: row for row in signal_rows}
    stock_names = set(stock_by_name)
    grouped: dict[str, dict[str, Any]] = {}

    for row in _load_knowledge_keywords(list(stock_names)):
        stock = stock_by_name.get(row["stock_name"])
        if not stock:
            continue
        _add_candidate(
            grouped,
            row.get("node_value"),
            stock,
            source="stock_knowledge_graph",
            weight=_safe_float(row.get("score")) or 0,
            stock_names=stock_names,
        )

    for stock in signal_rows:
        profile_terms = []
        profile_terms.extend(_split_profile_terms(stock.get("secondary_theme")))
        profile_terms.extend(_split_profile_terms(stock.get("related_themes")))
        if not profile_terms:
            profile_terms.extend(_split_profile_terms(stock.get("primary_theme")))
        for term in profile_terms:
            _add_candidate(
                grouped,
                term,
                stock,
                source="stock_profile",
                weight=30,
                stock_names=stock_names,
            )

    for row in _load_pdf_theme_keywords(list(stock_names)):
        stock = stock_by_name.get(row["stock_name"])
        if not stock:
            continue
        for term in _split_profile_terms(row.get("theme_name")):
            _add_candidate(
                grouped,
                term,
                stock,
                source="pdf_signal_item",
                weight=10,
                pdf_count=int(row.get("pdf_count") or 0),
                stock_names=stock_names,
            )

    for row in _load_news_subtheme_hits(list(stock_names), report_date):
        stock = stock_by_name.get(row["stock_name"])
        if not stock:
            continue
        for keyword in _extract_priority_keywords_from_text(row.get("news_text")):
            _add_candidate(
                grouped,
                keyword,
                stock,
                source="news_article",
                weight=50,
                stock_names=stock_names,
            )

    rankings: list[dict[str, Any]] = []
    for subtheme, entry in grouped.items():
        stocks = list(entry["stocks_by_name"].values())
        if not stocks:
            continue
        pdf_count = int(entry["pdf_count"] or 0)
        allowed, debug_only = _allow_final_subtheme(
            subtheme,
            stocks,
            pdf_count,
            stock_names,
        )
        if not allowed:
            continue
        if debug_only and not include_debug:
            continue
        ranked_stocks = sorted(stocks, key=_stock_sort_key, reverse=True)
        scores = [
            score
            for score in (_safe_float(row.get("investment_score")) for row in stocks)
            if score is not None
        ]
        average_score = sum(scores) / len(scores) if scores else 0
        leader = ranked_stocks[0]
        leader_score = _safe_float(leader.get("investment_score")) or 0
        stock_count_score = min(30, len(stocks) * 10)
        average_score_part = min(40, average_score * 0.4)
        leader_score_part = min(20, leader_score * 0.2)
        pdf_score_part = min(10, pdf_count)
        total_score = round(
            min(
                100,
                stock_count_score
                + average_score_part
                + leader_score_part
                + pdf_score_part,
            )
        )

        rankings.append(
            {
                "subtheme": subtheme,
                "score": int(total_score),
                "stock_count": len(stocks),
                "leader": leader.get("stock_name"),
                "leader_score": _safe_float(leader.get("investment_score")),
                "leader_grade": leader.get("investment_grade"),
                "stocks": [row.get("stock_name") for row in ranked_stocks],
                "stock_details": [
                    {
                        "stock_name": row.get("stock_name"),
                        "investment_score": _safe_float(row.get("investment_score")),
                        "investment_grade": row.get("investment_grade"),
                    }
                    for row in ranked_stocks
                ],
                "pdf_count": pdf_count,
                "debug_only": debug_only,
                "sources": sorted(entry["sources"]),
                "score_breakdown": {
                    "stock_count": round(stock_count_score, 2),
                    "average_investment": round(average_score_part, 2),
                    "leader_score": round(leader_score_part, 2),
                    "pdf_frequency": round(pdf_score_part, 2),
                },
            }
        )

    return sorted(
        rankings,
        key=lambda row: (
            row["score"],
            row["stock_count"],
            row["leader_score"] or 0,
            row["pdf_count"],
        ),
        reverse=True,
    )
