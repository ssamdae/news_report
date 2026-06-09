from __future__ import annotations

import json
from typing import Any


GROWTH_THEME_KEYWORDS = {
    "AI",
    "반도체",
    "HBM",
    "로봇",
    "휴머노이드",
    "전력",
    "전선",
    "원전",
    "방산",
    "조선",
    "바이오",
    "2차전지",
    "ESS",
    "데이터센터",
}

POSITIVE_KEYWORDS = {
    "수주",
    "공급계약",
    "실적",
    "영업이익",
    "흑자전환",
    "호실적",
    "AI",
    "반도체",
    "HBM",
    "로봇",
    "휴머노이드",
    "방산",
    "원전",
    "전력",
    "전선",
    "ESS",
    "데이터센터",
    "정책",
    "정부",
    "투자",
    "증설",
    "M&A",
    "인수",
    "합병",
    "계약",
}

IMPORTANT_POSITIVE_KEYWORDS = {
    "수주",
    "공급계약",
    "실적",
    "흑자전환",
    "AI",
    "반도체",
    "로봇",
    "정책",
}

NEGATIVE_KEYWORDS = {
    "적자",
    "소송",
    "감사의견",
    "불성실공시",
    "상장폐지",
    "횡령",
    "배임",
    "유상증자",
    "전환사채",
    "CB",
    "BW",
    "리스크",
    "급락",
}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _as_context_dict(value: dict | str | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"raw_text": value}
        return parsed if isinstance(parsed, dict) else {"raw_value": parsed}
    return {}


def _keyword_present(text: str, keyword: str) -> bool:
    return keyword.lower() in text.lower()


def _knowledge_keywords(context: dict[str, Any]) -> list[str]:
    keywords = context.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = [keywords]
    return [str(keyword).strip() for keyword in keywords if str(keyword).strip()]


def _calculate_pattern_score(
    pattern_stats: dict[str, Any],
    reasons: list[str],
) -> tuple[int, dict[str, Any]]:
    signal_count = _to_int(pattern_stats.get("signal_count"))
    day5_win_rate = _to_float(pattern_stats.get("day5_win_rate"))
    day5_avg_return = _to_float(pattern_stats.get("day5_avg_return"))
    min_return_5d = _to_float(pattern_stats.get("min_return_5d"))

    score = 0
    if signal_count >= 20:
        score += 12
    elif signal_count >= 15:
        score += 10
    elif signal_count >= 10:
        score += 7
    elif signal_count >= 5:
        score += 4

    if day5_win_rate is not None:
        if day5_win_rate >= 65:
            score += 12
        elif day5_win_rate >= 55:
            score += 10
        elif day5_win_rate >= 45:
            score += 6
        elif day5_win_rate >= 35:
            score += 3

    if day5_avg_return is not None:
        if day5_avg_return >= 7:
            score += 12
        elif day5_avg_return >= 5:
            score += 10
        elif day5_avg_return >= 3:
            score += 7
        elif day5_avg_return > 0:
            score += 4

    if min_return_5d is not None:
        if min_return_5d >= -15:
            score += 4
        elif min_return_5d >= -25:
            score += 2

    if signal_count:
        reasons.append(f"과거 {signal_count}회 출현")
    if day5_avg_return is not None:
        reasons.append(f"D+5 평균 수익률 {day5_avg_return:+.2f}%")
    if day5_win_rate is not None:
        reasons.append(f"D+5 상승확률 {day5_win_rate:.1f}%")

    debug = {
        "signal_count": signal_count,
        "source_signal_count": _to_int(pattern_stats.get("source_signal_count")),
        "source_pdf_count": _to_int(pattern_stats.get("source_pdf_count")),
        "day5_win_rate": day5_win_rate,
        "day5_avg_return": day5_avg_return,
        "min_return_5d": min_return_5d,
    }
    return int(min(score, 40)), debug


def _calculate_knowledge_score(
    context: dict[str, Any],
    pattern_stats: dict[str, Any],
    reasons: list[str],
) -> int:
    score = 0
    primary_theme = context.get("primary_theme")
    keywords = _knowledge_keywords(context)
    source_pdf_count = _to_int(pattern_stats.get("source_pdf_count"))

    if primary_theme:
        score += 8
        reasons.append(f"{primary_theme} 대표 테마와 연관")

    if source_pdf_count >= 20:
        score += 10
    elif source_pdf_count >= 10:
        score += 8
    elif source_pdf_count >= 5:
        score += 5

    if source_pdf_count:
        reasons.append(f"PDF 과거 사례 {source_pdf_count}회")

    keyword_count = len(keywords)
    if keyword_count >= 5:
        score += 7
    elif keyword_count >= 3:
        score += 5
    elif keyword_count >= 1:
        score += 3

    if keyword_count:
        reasons.append(f"지식맵 키워드 {keyword_count}개")

    keyword_text = " ".join([str(primary_theme or ""), *keywords])
    growth_matches = [
        keyword for keyword in GROWTH_THEME_KEYWORDS if _keyword_present(keyword_text, keyword)
    ]
    if growth_matches:
        score += 5
        reasons.append(f"{growth_matches[0]} 핵심 성장 테마와 연관")

    return int(min(score, 30))


def _calculate_news_score(
    news_text: str | None,
    ai_analysis_text: str | None,
    reasons: list[str],
) -> int:
    combined_text = f"{news_text or ''}\n{ai_analysis_text or ''}"
    score = 0
    positive_matches = []
    negative_matches = []

    for keyword in POSITIVE_KEYWORDS:
        if not _keyword_present(combined_text, keyword):
            continue
        positive_matches.append(keyword)
        score += 5 if keyword in IMPORTANT_POSITIVE_KEYWORDS else 3

    for keyword in NEGATIVE_KEYWORDS:
        if _keyword_present(combined_text, keyword):
            negative_matches.append(keyword)
            score -= 5

    if positive_matches:
        reasons.append("긍정 키워드: " + ", ".join(sorted(positive_matches)[:5]))
    if negative_matches:
        reasons.append("주의 키워드: " + ", ".join(sorted(negative_matches)[:5]))

    return int(_clamp(score, 0, 30))


def _grade_from_score(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def calculate_investment_grade(
    stock_name: str,
    news_text: str | None = None,
    ai_analysis_text: str | None = None,
    knowledge_context: dict | str | None = None,
    pattern_stats: dict | None = None,
) -> dict:
    context = _as_context_dict(knowledge_context)
    pattern_stats = pattern_stats or {}
    grade_reasons: list[str] = []

    pattern_score, debug = _calculate_pattern_score(pattern_stats, grade_reasons)
    knowledge_score = _calculate_knowledge_score(
        context,
        pattern_stats,
        grade_reasons,
    )
    news_score = _calculate_news_score(news_text, ai_analysis_text, grade_reasons)

    total_score = round(
        _clamp(pattern_score + knowledge_score + news_score, 0, 100),
        2,
    )

    return {
        "investment_score": total_score,
        "investment_grade": _grade_from_score(total_score),
        "grade_reasons": grade_reasons[:6],
        "score_breakdown": {
            "pattern": pattern_score,
            "knowledge": knowledge_score,
            "news": news_score,
        },
        "debug": {
            "stock_name": stock_name,
            **debug,
        },
    }
