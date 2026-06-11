from __future__ import annotations

import json
from typing import Any


GROWTH_THEME_KEYWORDS = {
    "AI",
    "로봇",
    "휴머노이드",
    "반도체",
    "HBM",
    "전력",
    "전선",
    "원전",
    "방산",
    "조선",
    "바이오",
    "이차전지",
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

TOP_NEWS_KEYWORDS = {
    "수주": 12,
    "공급계약": 12,
    "대규모 공급": 12,
    "독점 공급": 12,
    "기술수출": 12,
    "라이선스아웃": 12,
    "LO": 10,
    "특허": 10,
    "물질특허": 14,
    "FDA": 12,
    "임상": 8,
    "승인": 10,
    "SOCAMM": 14,
    "HBM": 12,
    "AI메모리": 12,
    "AI 메모리": 12,
    "AI반도체": 12,
    "데이터센터": 10,
    "유리기판": 10,
    "전력반도체": 10,
    "정부정책": 10,
    "정책": 8,
    "국책과제": 10,
    "M&A": 12,
    "인수합병": 12,
}

MID_NEWS_KEYWORDS = {
    "영업이익": 6,
    "흑자전환": 7,
    "증설": 5,
    "공장": 4,
    "양산": 6,
    "로봇": 5,
    "휴머노이드": 7,
    "이차전지": 5,
    "2차전지": 5,
    "전해액": 5,
    "원전": 5,
    "방산": 5,
    "우주항공": 5,
}

LOW_NEWS_KEYWORDS = {
    "주가 상승": 2,
    "급등": 2,
    "강세": 2,
    "거래량 증가": 2,
    "특징주": 2,
    "장중 상승": 2,
    "인기 검색 종목": 1,
}

NEGATIVE_KEYWORDS = {
    "적자": -8,
    "영업손실": -10,
    "관리종목": -18,
    "상장폐지": -20,
    "감사의견": -15,
    "횡령": -18,
    "배임": -18,
    "불성실공시": -12,
    "유상증자": -8,
    "전환사채": -8,
    "CB": -8,
    "BW": -8,
    "소송": -10,
    "임상 실패": -20,
    "허가 반려": -18,
    "계약 해지": -15,
    "급락": -8,
}

CONTRACT_KEYWORDS = {"수주", "공급계약", "대규모 공급", "독점 공급", "계약"}
POLICY_KEYWORDS = {"정부정책", "정책", "국책과제", "정부"}
TECH_KEYWORDS = {
    "특허",
    "물질특허",
    "SOCAMM",
    "HBM",
    "AI메모리",
    "AI 메모리",
    "AI반도체",
    "데이터센터",
    "유리기판",
    "전력반도체",
}
BIO_TECH_KEYWORDS = {"기술수출", "라이선스아웃", "LO", "FDA", "임상", "승인", "ADC"}
EARNINGS_KEYWORDS = {"실적", "영업이익", "흑자전환"}
PRICE_ONLY_KEYWORDS = set(LOW_NEWS_KEYWORDS)
RISK_KEYWORDS = set(NEGATIVE_KEYWORDS)
WEAK_NEWS_KEYWORDS = {
    "실적": 2,
    "고객사": 2,
    "투자": 2,
}
SPECIFIC_EARNINGS_KEYWORDS = {
    "영업이익": 6,
    "매출 증가": 5,
    "매출액": 4,
    "흑자전환": 7,
    "어닝서프라이즈": 7,
    "실적 개선": 5,
    "분기 최대": 6,
    "사상 최대": 7,
    "컨센서스 상회": 6,
}
MARKET_SUMMARY_TITLE_KEYWORDS = {
    "시황",
    "마감시황",
    "증시",
    "코스피",
    "코스닥",
    "장중",
    "마감",
    "특징주 모음",
    "상승 종목",
    "하락 종목",
    "인기 검색 종목",
    "외국인 순매수",
    "기관 순매수",
    "거래대금 상위",
    "급등주",
    "강세주",
}
CUSTOMER_CONTEXT_KEYWORDS = {
    "신규 고객사": 6,
    "고객사 확대": 6,
    "공급계약": 8,
    "수주": 8,
    "납품": 6,
    "양산": 6,
    "삼성전자 공급": 8,
    "SK하이닉스 공급": 8,
    "엔비디아 공급": 8,
    "TSMC 공급": 8,
}
MAJOR_COMPANY_KEYWORDS = {
    "삼성전자": 6,
    "SK하이닉스": 6,
    "엔비디아": 6,
    "NVIDIA": 6,
    "TSMC": 6,
    "마이크론": 6,
    "브로드컴": 6,
    "애플": 5,
    "테슬라": 5,
    "현대차": 5,
    "LG에너지솔루션": 6,
}
STRONG_COMPANY_RELATION_TERMS = {
    "공급",
    "공급계약",
    "수주",
    "납품",
    "양산",
    "협력",
    "파트너",
    "고객사로",
    "고객사에",
    "고객사 공급",
    "밸류체인",
    "장비",
    "소재",
    "부품",
    "테스트",
    "검사",
    "후공정",
    "전공정",
}
MAJOR_COMPANY_ALLOWED_PRIMARY_THEME = {
    "삼성전자": {"반도체", "AI/로봇", "이차전지", "전력"},
    "SK하이닉스": {"반도체", "AI/로봇"},
    "엔비디아": {"반도체", "AI/로봇", "전력"},
    "NVIDIA": {"반도체", "AI/로봇", "전력"},
    "TSMC": {"반도체"},
    "마이크론": {"반도체"},
    "브로드컴": {"반도체", "AI/로봇"},
    "애플": {"반도체", "AI/로봇", "소비재"},
    "테슬라": {"이차전지", "AI/로봇", "전력"},
    "현대차": {"자동차", "이차전지", "AI/로봇"},
    "LG에너지솔루션": {"이차전지"},
}

NEWS_KEYWORD_ALLOWED_PRIMARY_THEME = {
    "HBM": {"반도체"},
    "AI반도체": {"반도체", "AI/로봇"},
    "AI 메모리": {"반도체", "AI/로봇"},
    "AI메모리": {"반도체", "AI/로봇"},
    "SOCAMM": {"반도체", "AI/로봇"},
    "데이터센터": {"반도체", "AI/로봇", "전력"},
    "반도체장비": {"반도체"},
    "반도체 장비": {"반도체"},
    "유리기판": {"반도체"},
    "전력반도체": {"반도체", "전력"},
    "이차전지": {"이차전지"},
    "2차전지": {"이차전지"},
    "2차 전지": {"이차전지"},
    "전해액": {"이차전지"},
    "전고체": {"이차전지"},
    "ESS": {"이차전지", "전력"},
    "리튬": {"이차전지"},
    "로봇": {"AI/로봇"},
    "휴머노이드": {"AI/로봇"},
    "산업용로봇": {"AI/로봇"},
    "스마트팩토리": {"AI/로봇", "반도체"},
    "ADC": {"바이오"},
    "기술수출": {"바이오"},
    "라이선스아웃": {"바이오"},
    "특허": {"바이오", "반도체", "AI/로봇"},
    "물질특허": {"바이오"},
    "FDA": {"바이오"},
    "임상": {"바이오"},
    "승인": {"바이오"},
    "방산": {"방산", "우주항공", "개별주"},
    "우주항공": {"우주항공", "방산", "개별주"},
    "원전": {"원전", "전력", "개별주"},
    "전력기기": {"전력"},
    "전력망": {"전력"},
}

NEWS_KEYWORD_ALIASES = {
    "AI 메모리": "AI메모리",
    "반도체 장비": "반도체장비",
    "2차전지": "이차전지",
    "2차 전지": "이차전지",
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


def _dedupe_keep_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def normalize_primary_theme(theme: Any) -> str:
    text = str(theme or "").strip()
    compact = text.replace(" ", "")
    if compact in {"AI로봇", "로봇", "AI/로봇"}:
        return "AI/로봇"
    if compact in {"2차전지", "2차전지소재", "이차전지"}:
        return "이차전지"
    if compact in {"제약바이오", "바이오"}:
        return "바이오"
    if compact in {"반도체장비"}:
        return "반도체"
    return text


def _normalize_news_keyword(keyword: str) -> str:
    return NEWS_KEYWORD_ALIASES.get(keyword, keyword)


def _news_keyword_theme_allowed(
    keyword: str,
    stock_primary_theme: str | None,
) -> bool:
    normalized_keyword = _normalize_news_keyword(keyword)
    allowed_themes = (
        NEWS_KEYWORD_ALLOWED_PRIMARY_THEME.get(keyword)
        or NEWS_KEYWORD_ALLOWED_PRIMARY_THEME.get(normalized_keyword)
    )
    if not allowed_themes:
        return True
    primary_theme = normalize_primary_theme(stock_primary_theme)
    if not primary_theme:
        return False
    return primary_theme in {
        normalize_primary_theme(theme)
        for theme in allowed_themes
    }


def _major_company_primary_theme_allowed(
    keyword: str,
    stock_primary_theme: str | None,
) -> bool:
    allowed_themes = MAJOR_COMPANY_ALLOWED_PRIMARY_THEME.get(keyword)
    if not allowed_themes:
        return True
    primary_theme = normalize_primary_theme(stock_primary_theme)
    if not primary_theme:
        return False
    return primary_theme in {
        normalize_primary_theme(theme)
        for theme in allowed_themes
    }


def _keyword_near_stock_name(text: str, stock_name: str, keyword: str, radius: int = 80) -> bool:
    if not stock_name or not keyword:
        return False
    stock_index = text.find(stock_name)
    while stock_index != -1:
        start = max(0, stock_index - radius)
        end = min(len(text), stock_index + len(stock_name) + radius)
        if keyword in text[start:end]:
            return True
        stock_index = text.find(stock_name, stock_index + len(stock_name))
    return False


def _major_company_context_valid(
    keyword: str,
    stock_name: str | None,
    news_items: list[dict[str, Any]],
) -> bool:
    for item in news_items:
        title = str(item.get("title") or "")
        body = " ".join(
            str(item.get(key) or "")
            for key in ("description", "ai_summary", "summary")
        )
        item_text = f"{title} {body}"
        if stock_name and stock_name in title and keyword in title:
            return True
        if stock_name and _keyword_near_stock_name(body, stock_name, keyword):
            return True
        if keyword in item_text and any(
            connector in item_text
            for connector in STRONG_COMPANY_RELATION_TERMS
        ):
            return True
    return False


def _is_market_summary_title(title: str) -> bool:
    return any(keyword in title for keyword in MARKET_SUMMARY_TITLE_KEYWORDS)


def _keyword_near_text(text: str, anchor: str, keyword: str, radius: int = 80) -> bool:
    if not anchor or not keyword:
        return False
    keyword_index = text.find(keyword)
    while keyword_index != -1:
        start = max(0, keyword_index - radius)
        end = min(len(text), keyword_index + len(keyword) + radius)
        if anchor in text[start:end]:
            return True
        keyword_index = text.find(keyword, keyword_index + len(keyword))
    return False


def _earnings_context_valid(
    keyword: str,
    stock_name: str | None,
    news_items: list[dict[str, Any]],
) -> bool:
    if not stock_name:
        return False
    for item in news_items:
        title = str(item.get("title") or "")
        body = " ".join(
            str(item.get(key) or "")
            for key in ("description", "ai_summary", "summary")
        )
        item_text = f"{title} {body}"
        if not _keyword_present(item_text, keyword):
            continue
        if stock_name in title and keyword in title:
            return True
        if _keyword_near_stock_name(body, stock_name, keyword):
            return True
        if _keyword_near_text(body, stock_name, keyword):
            return True
        if not _is_market_summary_title(title) and stock_name in item_text:
            return True
    return False


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
        if day5_win_rate >= 70:
            score += 15
        elif day5_win_rate >= 60:
            score += 12
        elif day5_win_rate >= 50:
            score += 8
        elif day5_win_rate >= 40:
            score += 5

    if day5_avg_return is not None:
        if day5_avg_return >= 7:
            score += 18
        elif day5_avg_return >= 5:
            score += 15
        elif day5_avg_return >= 3:
            score += 10
        elif day5_avg_return > 0:
            score += 5

    if min_return_5d is not None:
        if min_return_5d >= -10:
            score += 5
        elif min_return_5d >= -20:
            score += 3
        elif min_return_5d >= -30:
            score += 1

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
    return int(min(score, 50)), debug


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
        score += 6
        reasons.append(f"{primary_theme} 대표 테마와 연관")

    if source_pdf_count >= 20:
        score += 8
    elif source_pdf_count >= 10:
        score += 6
    elif source_pdf_count >= 5:
        score += 4

    if source_pdf_count:
        reasons.append(f"PDF 과거 사례 {source_pdf_count}회")

    keyword_count = len(keywords)
    if keyword_count >= 5:
        score += 5
    elif keyword_count >= 3:
        score += 4
    elif keyword_count >= 1:
        score += 3

    if keyword_count:
        reasons.append(f"지식맵 키워드 {keyword_count}개")

    keyword_text = " ".join([str(primary_theme or ""), *keywords])
    growth_matches = [
        keyword for keyword in GROWTH_THEME_KEYWORDS if _keyword_present(keyword_text, keyword)
    ]
    if growth_matches:
        score += 6
        reasons.append(f"{growth_matches[0]} 핵심 성장 테마와 연관")

    return int(min(score, 25))


def _news_item_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "description", "ai_summary", "summary")
    )


def calculate_news_importance_score(
    news_items: list[dict[str, Any]] | None = None,
    news_text: str | None = None,
    ai_analysis_text: str | None = None,
    stock_name: str | None = None,
    stock_primary_theme: str | None = None,
) -> dict[str, Any]:
    news_items = news_items or []
    combined_parts = [news_text or "", ai_analysis_text or ""]
    combined_parts.extend(_news_item_text(item) for item in news_items)
    combined_text = "\n".join(combined_parts)

    score = 0
    top_matches: list[str] = []
    mid_matches: list[str] = []
    low_matches: list[str] = []
    negative_matches: list[str] = []
    weak_matches: list[str] = []
    ignored_theme_matches: list[str] = []
    ignored_company_matches: list[str] = []
    ignored_earnings_matches: list[str] = []
    specific_earnings_matches: list[str] = []
    news_types: set[str] = set()
    matched_titles: list[str] = []

    def add_titles_for_keyword(keyword: str) -> None:
        for item in news_items:
            title = str(item.get("title") or "").strip()
            if title and _keyword_present(_news_item_text(item), keyword):
                matched_titles.append(title)

    def keyword_allowed(keyword: str) -> bool:
        if _news_keyword_theme_allowed(keyword, stock_primary_theme):
            return True
        ignored_theme_matches.append(_normalize_news_keyword(keyword))
        return False

    for keyword, weight in TOP_NEWS_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        if not keyword_allowed(keyword):
            continue
        top_matches.append(keyword)
        score += weight
        add_titles_for_keyword(keyword)

    for keyword, weight in MID_NEWS_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        if not keyword_allowed(keyword):
            continue
        mid_matches.append(keyword)
        score += weight
        add_titles_for_keyword(keyword)

    for keyword, weight in SPECIFIC_EARNINGS_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        if not keyword_allowed(keyword):
            continue
        if not _earnings_context_valid(keyword, stock_name, news_items):
            ignored_earnings_matches.append(keyword)
            continue
        specific_earnings_matches.append(keyword)
        mid_matches.append(keyword)
        score += weight
        add_titles_for_keyword(keyword)

    for keyword, weight in CUSTOMER_CONTEXT_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        if not keyword_allowed(keyword):
            continue
        mid_matches.append(keyword)
        score += weight
        add_titles_for_keyword(keyword)

    for keyword, weight in MAJOR_COMPANY_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        if not _major_company_primary_theme_allowed(keyword, stock_primary_theme):
            ignored_company_matches.append(keyword)
            continue
        if not _major_company_context_valid(keyword, stock_name, news_items):
            ignored_company_matches.append(keyword)
            continue
        if not keyword_allowed(keyword):
            continue
        mid_matches.append(keyword)
        score += weight
        add_titles_for_keyword(keyword)

    for keyword, weight in WEAK_NEWS_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        weak_matches.append(keyword)
        score += weight
        add_titles_for_keyword(keyword)

    for keyword, weight in LOW_NEWS_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        low_matches.append(keyword)
        score += weight
        add_titles_for_keyword(keyword)

    for keyword, penalty in NEGATIVE_KEYWORDS.items():
        if not _keyword_present(combined_text, keyword):
            continue
        negative_matches.append(keyword)
        score += penalty
        add_titles_for_keyword(keyword)

    matched_positive = set(top_matches + mid_matches + low_matches)
    if matched_positive & CONTRACT_KEYWORDS:
        news_types.add("CONTRACT")
    if matched_positive & POLICY_KEYWORDS:
        news_types.add("POLICY")
    if matched_positive & TECH_KEYWORDS:
        news_types.add("TECH")
    if matched_positive & BIO_TECH_KEYWORDS:
        news_types.add("BIO_TECH")
    if set(specific_earnings_matches) & EARNINGS_KEYWORDS or specific_earnings_matches:
        news_types.add("EARNINGS")
    if low_matches and not top_matches and not mid_matches:
        news_types.add("PRICE_ONLY")
    if negative_matches:
        news_types.add("RISK")

    high_importance_count = len(set(top_matches))
    if high_importance_count >= 2 and "RISK" not in news_types:
        score = max(score, 15)
    if ({"TECH", "CONTRACT"} & news_types) and "RISK" not in news_types:
        score = max(score, 12)
    if news_types == {"PRICE_ONLY"}:
        score = min(score, 5)
    if news_types == {"EARNINGS"}:
        score = min(score, 15 if specific_earnings_matches else 8)
    elif not ({"TECH", "CONTRACT", "BIO_TECH", "POLICY"} & news_types):
        if specific_earnings_matches:
            score = min(score, 15)

    important_keywords = _dedupe_keep_order(top_matches + mid_matches)
    return {
        "score": int(_clamp(score, 0, 25)),
        "news_types": sorted(news_types),
        "important_news_keywords": important_keywords[:12],
        "weak_news_keywords": _dedupe_keep_order(weak_matches)[:8],
        "ignored_theme_keywords": _dedupe_keep_order(ignored_theme_matches)[:8],
        "ignored_company_keywords": _dedupe_keep_order(ignored_company_matches)[:8],
        "ignored_earnings_keywords": _dedupe_keep_order(ignored_earnings_matches)[:8],
        "specific_earnings_keywords": _dedupe_keep_order(specific_earnings_matches)[:8],
        "low_importance_keywords": _dedupe_keep_order(low_matches)[:8],
        "negative_news_keywords": _dedupe_keep_order(negative_matches)[:8],
        "matched_news_titles": _dedupe_keep_order(matched_titles)[:5],
    }


def _calculate_news_score(
    news_text: str | None,
    ai_analysis_text: str | None,
    reasons: list[str],
    news_items: list[dict[str, Any]] | None = None,
    stock_name: str | None = None,
    stock_primary_theme: str | None = None,
) -> tuple[int, dict[str, Any]]:
    result = calculate_news_importance_score(
        news_items=news_items,
        news_text=news_text,
        ai_analysis_text=ai_analysis_text,
        stock_name=stock_name,
        stock_primary_theme=stock_primary_theme,
    )
    important_keywords = result.get("important_news_keywords") or []
    negative_keywords = result.get("negative_news_keywords") or []
    if important_keywords:
        reasons.append("뉴스 모멘텀: " + ", ".join(important_keywords[:5]))
    if negative_keywords:
        reasons.append("뉴스 리스크: " + ", ".join(negative_keywords[:5]))
    return int(result["score"]), result


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
    news_items: list[dict[str, Any]] | None = None,
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
    news_score, news_debug = _calculate_news_score(
        news_text,
        ai_analysis_text,
        grade_reasons,
        news_items=news_items,
        stock_name=stock_name,
        stock_primary_theme=context.get("primary_theme"),
    )

    total_score = round(
        _clamp(pattern_score + knowledge_score + news_score, 0, 100),
        2,
    )
    pattern_boost_applied = False
    risk_cap_applied = False
    risk_cap_reason = None

    signal_count = _to_int(pattern_stats.get("signal_count"))
    day5_win_rate = _to_float(pattern_stats.get("day5_win_rate"))
    day5_avg_return = _to_float(pattern_stats.get("day5_avg_return"))
    min_return_5d = _to_float(pattern_stats.get("min_return_5d"))

    if (
        signal_count >= 15
        and day5_win_rate is not None
        and day5_win_rate >= 65
        and day5_avg_return is not None
        and day5_avg_return >= 5
        and total_score < 65
    ):
        total_score = 65
        pattern_boost_applied = True
        grade_reasons.insert(0, "과거 패턴 성과 우수로 등급 보정")

    investment_grade = _grade_from_score(total_score)
    if news_score <= 5 and min_return_5d is not None and min_return_5d <= -25:
        if investment_grade == "A":
            investment_grade = "B"
            risk_cap_applied = True
            risk_cap_reason = "뉴스 모멘텀 제한 및 5일 최대손실 리스크"
            grade_reasons.insert(0, "변동성 리스크로 등급 상단 제한")

    if (
        day5_avg_return is not None
        and day5_avg_return < 0
        and min_return_5d is not None
        and min_return_5d <= -30
    ):
        if investment_grade in {"A", "B"}:
            investment_grade = "C"
            risk_cap_applied = True
            risk_cap_reason = "D+5 평균 수익률 부진 및 5일 최대손실 리스크"
            grade_reasons.insert(0, "변동성 리스크로 등급 상단 제한")

    return {
        "investment_score": total_score,
        "investment_grade": investment_grade,
        "grade_reasons": grade_reasons[:6],
        "score_breakdown": {
            "pattern": pattern_score,
            "knowledge": knowledge_score,
            "news": news_score,
        },
        "debug": {
            "stock_name": stock_name,
            **debug,
            "pattern_boost_applied": pattern_boost_applied,
            "risk_cap_applied": risk_cap_applied,
            "risk_cap_reason": risk_cap_reason,
            **news_debug,
        },
    }
