from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from database.db import get_connection
from database.pattern_repository import get_stock_pattern_stats
from report.subtheme_ranking_engine import build_subtheme_rankings
from report.theme_ranking_engine import build_theme_rankings


REPORT_ROOT = Path("reports")


def _fetch_one(sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))


def _fetch_all(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _text(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text or "-"


def _link_paragraph(url: Any, label: str, style: Any) -> Any:
    from html import escape

    from reportlab.platypus import Paragraph

    href = escape(_text(url), quote=True)
    text = escape(label)
    return Paragraph(f'<link href="{href}" color="blue">{text}</link>', style)


def _format_number(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _format_score(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return str(value)


def _format_trading_value_eok(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) / 100_000_000:,.0f}억"
    except (TypeError, ValueError):
        return str(value)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truncate_with_ellipsis(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def _news_summary_text(row: dict[str, Any]) -> str:
    summary = _text(row.get("ai_summary"))
    if summary != "-":
        compact = " ".join(summary.replace("\n", " ").split())
        sentences = compact.split(". ")
        if len(sentences) > 2:
            compact = ". ".join(sentences[:2]).rstrip(".") + "."
        return _truncate_with_ellipsis(compact, 60)
    description = _text(row.get("description"))
    if description == "-":
        return ""
    compact = " ".join(description.replace("\n", " ").split())
    return _truncate_with_ellipsis(compact, 60)


def _knowledge_points_text(value: Any) -> str:
    text = _text(value)
    if text == "-":
        return text

    compact = " ".join(text.replace("\n", " ").split())
    sentences = compact.split(". ")
    if len(sentences) > 3:
        compact = ". ".join(sentences[:3]).rstrip(".") + "."
    return _truncate_with_ellipsis(compact, 260)


def _knowledge_map_text(
    stock_name: str,
    signal: dict[str, Any],
    analysis: dict[str, Any],
    pattern_stats: dict[str, Any],
) -> str:
    from database.news_repository import get_stock_knowledge_context

    context = get_stock_knowledge_context(stock_name)
    primary_theme = (
        context.get("primary_theme")
        or signal.get("primary_theme")
        or "-"
    )
    keywords = context.get("keywords") or []
    keyword_text = ", ".join(str(keyword) for keyword in keywords[:5]) or "-"
    pdf_count = int(
        pattern_stats.get("source_pdf_count")
        or context.get("pdf_appear_count")
        or 0
    )
    interpretation = _knowledge_points_text(analysis.get("knowledge_points"))
    if interpretation == "-":
        interpretation = "지식맵 데이터가 부족해 반복 테마 판단은 제한됩니다."

    return "\n".join(
        [
            f"대표테마: {primary_theme}",
            f"과거 PDF 출현: {pdf_count}회",
            f"관련 키워드: {keyword_text}",
            f"해석: {_truncate_with_ellipsis(interpretation, 180)}",
        ]
    )


def _pattern_stats_from_analysis(analysis: dict[str, Any] | None) -> dict[str, Any]:
    if not analysis:
        return {}
    return {
        "signal_count": analysis.get("pattern_signal_count"),
        "source_signal_count": analysis.get("source_signal_count"),
        "source_pdf_count": analysis.get("source_pdf_count"),
        "next_day_win_rate": analysis.get("next_day_win_rate"),
        "next_day_avg_return": analysis.get("next_day_avg_return"),
        "day3_win_rate": analysis.get("day3_win_rate"),
        "day3_avg_return": analysis.get("day3_avg_return"),
        "day5_win_rate": analysis.get("day5_win_rate"),
        "day5_avg_return": analysis.get("day5_avg_return"),
        "max_return_5d": analysis.get("max_return_5d"),
        "min_return_5d": analysis.get("min_return_5d"),
    }


def _format_pattern_pct(value: Any, show_sign: bool = False) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if show_sign:
        return f"{number:+.1f}%"
    return f"{number:.1f}%"


def _pattern_interpretation_text(value: Any) -> str:
    text = _text(value)
    if text == "-":
        return ""

    compact = " ".join(text.replace("\n", " ").split())
    sentences = compact.split(". ")
    if len(sentences) > 3:
        compact = ". ".join(sentences[:3]).rstrip(".") + "."
    return _truncate_with_ellipsis(compact, 220)


def _pattern_stats_text(stats: dict[str, Any], interpretation: Any) -> str:
    signal_count = int(stats.get("signal_count") or 0)
    if signal_count <= 0:
        return "과거 500억봉 패턴 통계가 부족하여 신뢰도 있는 수익률 판단은 제한됩니다."

    source_signal_count = int(stats.get("source_signal_count") or 0)
    source_pdf_count = int(stats.get("source_pdf_count") or 0)
    lines = [
        f"발생횟수: {signal_count}회",
        f"* 실시간 조건식: {source_signal_count}회",
        f"* PDF 과거 강세: {source_pdf_count}회",
        (
            "D+1 승률/평균: "
            f"{_format_pattern_pct(stats.get('next_day_win_rate'))} / "
            f"{_format_pattern_pct(stats.get('next_day_avg_return'), show_sign=True)}"
        ),
        (
            "D+3 승률/평균: "
            f"{_format_pattern_pct(stats.get('day3_win_rate'))} / "
            f"{_format_pattern_pct(stats.get('day3_avg_return'), show_sign=True)}"
        ),
        (
            "D+5 승률/평균: "
            f"{_format_pattern_pct(stats.get('day5_win_rate'))} / "
            f"{_format_pattern_pct(stats.get('day5_avg_return'), show_sign=True)}"
        ),
        (
            "5D 최대/최소: "
            f"{_format_pattern_pct(stats.get('max_return_5d'), show_sign=True)} / "
            f"{_format_pattern_pct(stats.get('min_return_5d'), show_sign=True)}"
        ),
    ]
    if signal_count < 3:
        lines.append("※ 표본 부족으로 통계 신뢰도는 낮습니다.")

    interpretation_text = _pattern_interpretation_text(interpretation)
    if interpretation_text:
        lines.append(f"AI 해석: {interpretation_text}")

    return "\n".join(lines)


def _register_korean_font() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    font_candidates = [
        (
            "NotoSansKR",
            "fonts/NotoSansKR-Regular.ttf",
            "NotoSansKRBold",
            "fonts/NotoSansKR-Bold.ttf",
        ),
        (
            "NotoSansKR",
            "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
            "NotoSansKRBold",
            "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.ttf",
        ),
        (
            "NotoSansKR",
            "/usr/share/fonts/opentype/noto/NotoSansKR-Regular.otf",
            "NotoSansKRBold",
            "/usr/share/fonts/opentype/noto/NotoSansKR-Bold.otf",
        ),
        (
            "NanumGothic",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "NanumGothicBold",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        ),
        (
            "AppleGothic",
            "/System/Library/Fonts/AppleGothic.ttf",
            "AppleGothic",
            "/System/Library/Fonts/AppleGothic.ttf",
        ),
        (
            "NotoSansCJK",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "NotoSansCJKBold",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        ),
    ]
    for font_name, font_path, bold_name, bold_path in font_candidates:
        path = Path(font_path)
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
            if Path(bold_path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                except Exception:
                    print(
                        "WARNING: Bold font not found. "
                        "Section titles may not appear bold."
                    )
                    bold_name = font_name
            else:
                print(
                    "WARNING: Bold font not found. "
                    "Section titles may not appear bold."
                )
                bold_name = font_name
            return font_name, bold_name
        except Exception:
            continue

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
        print("WARNING: Bold font not found. Section titles may not appear bold.")
        return "HYSMyeongJo-Medium", "HYSMyeongJo-Medium"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _build_styles(font_name: str, bold_font_name: str) -> dict[str, Any]:
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "KoreanTitle",
            parent=styles["Title"],
            fontName=bold_font_name,
            fontSize=22,
            leading=30,
            spaceAfter=24,
            alignment=1,
        ),
        "heading": ParagraphStyle(
            "KoreanHeading",
            parent=styles["Heading2"],
            fontName=bold_font_name,
            fontSize=15,
            leading=20,
            spaceBefore=18,
            spaceAfter=10,
        ),
        "stock_heading": ParagraphStyle(
            "KoreanStockHeading",
            parent=styles["Heading3"],
            fontName=bold_font_name,
            fontSize=13,
            leading=18,
            spaceBefore=10,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "KoreanSection",
            parent=styles["Heading3"],
            fontName=bold_font_name,
            fontSize=12,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "KoreanBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=14,
            spaceAfter=8,
        ),
        "table_header": ParagraphStyle(
            "KoreanTableHeader",
            parent=styles["BodyText"],
            fontName=bold_font_name,
            fontSize=8,
            leading=11,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "KoreanSmall",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=7,
            leading=9,
            spaceAfter=2,
        ),
    }


def _paragraph(text: Any, style: Any) -> Any:
    from html import escape

    from reportlab.platypus import Paragraph

    escaped = escape(_text(text)).replace("\n", "<br/>")
    return Paragraph(escaped, style)


def _add_report_section(
    story: list[Any],
    title: str,
    value: Any,
    styles: dict[str, Any],
) -> None:
    from reportlab.platypus import Paragraph, Spacer

    story.append(Paragraph(title, styles["section"]))
    story.append(_paragraph(value, styles["body"]))
    story.append(Spacer(1, 6))


def _market_strength_text(daily_theme: dict[str, Any]) -> str:
    return _market_strength_text_from_inputs(daily_theme, [], [])


def _market_strength_text_from_inputs(
    daily_theme: dict[str, Any],
    signals: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
) -> str:
    investment_scores = [
        score
        for score in (_safe_float(row.get("investment_score")) for row in analyses)
        if score is not None
    ]
    average_score = (
        sum(investment_scores) / len(investment_scores)
        if investment_scores
        else _safe_float(daily_theme.get("confidence_score")) or 0
    )
    grade_count = sum(
        1
        for row in analyses
        if str(row.get("investment_grade") or "") in {"A", "B"}
    )
    signal_count = len(signals)
    theme_counts: dict[str, int] = {}
    for row in signals:
        theme = _text(row.get("primary_theme"))
        if theme != "-":
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    concentration = (
        max(theme_counts.values()) / signal_count
        if signal_count and theme_counts
        else 0
    )

    strength_score = average_score
    strength_score += min(10, grade_count * 2)
    strength_score += min(8, signal_count)
    strength_score += concentration * 10

    if strength_score >= 85:
        stars = "★★★★★"
    elif strength_score >= 70:
        stars = "★★★★☆"
    elif strength_score >= 55:
        stars = "★★★☆☆"
    else:
        stars = "★★☆☆☆"

    strong_themes = _text(daily_theme.get("strong_themes"))
    detail = (
        f"평균 투자점수 {average_score:.1f}점, "
        f"B등급 이상 {grade_count}개, 500억봉 {signal_count}개 기준"
    )
    if strong_themes != "-":
        detail = f"{detail}\n{strong_themes}"
    return f"{stars}\n{detail}"


def _leading_theme_text(daily_theme: dict[str, Any]) -> str:
    return _leading_theme_text_from_inputs(daily_theme, [])


def _leading_theme_text_from_inputs(
    daily_theme: dict[str, Any],
    signals: list[dict[str, Any]],
) -> str:
    theme_rankings = _text(daily_theme.get("theme_rankings"))
    if theme_rankings != "-":
        return theme_rankings
    strong_themes = _text(daily_theme.get("strong_themes"))
    if strong_themes != "-":
        return strong_themes

    grouped: dict[str, list[str]] = {}
    for row in signals:
        theme = _text(row.get("primary_theme"))
        stock_name = _text(row.get("stock_name"))
        if theme == "-" or stock_name == "-":
            continue
        grouped.setdefault(theme, []).append(stock_name)
    if not grouped:
        return "당일 500억봉 종목의 대표테마 데이터가 부족합니다."

    ranked = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
    return "\n".join(
        f"{index}. {theme}: {', '.join(stocks[:5])}"
        for index, (theme, stocks) in enumerate(ranked[:5], start=1)
    )


def _theme_stock_label(
    stock_name: Any,
    grade: Any,
    score: Any,
) -> str:
    name_text = _text(stock_name)
    grade_text = _text(grade)
    score_value = _safe_float(score)
    if grade_text == "-" and score_value is None:
        return name_text
    if score_value is None:
        return f"{name_text} {grade_text}"
    return f"{name_text} {grade_text}{score_value:.0f}"


def _theme_ranking_text(theme_rankings: list[dict[str, Any]]) -> str:
    if not theme_rankings:
        return "주도 테마 랭킹을 산출할 500억봉 종목 데이터가 부족합니다."

    lines: list[str] = []
    for index, row in enumerate(theme_rankings[:5], start=1):
        lines.append(
            f"{index}위 {row['theme']} ({row['theme_score']}점)"
            f" / 종목 {row['stock_count']}개"
        )
        lines.append(
            "대장주: "
            + _theme_stock_label(
                row.get("leader"),
                row.get("leader_grade"),
                row.get("leader_score"),
            )
        )
        follower_details = row.get("follower_details") or []
        if follower_details:
            followers = [
                _theme_stock_label(
                    follower.get("stock_name"),
                    follower.get("investment_grade"),
                    follower.get("investment_score"),
                )
                for follower in follower_details
            ]
        else:
            followers = [str(name) for name in (row.get("followers") or [])]
        lines.append("후속주: " + (", ".join(followers) if followers else "-"))
        lines.append(
            "구성: "
            f"평균 투자점수 {row.get('average_investment_score', 0):.1f}, "
            f"B등급 이상 {row.get('ab_grade_count', 0)}개, "
            f"거래대금 비중 {row.get('trading_share', 0):.1f}%"
        )
        lines.append("")
    return "\n".join(lines).strip()


def _subtheme_ranking_text(subtheme_rankings: list[dict[str, Any]]) -> str:
    if not subtheme_rankings:
        return "주도 서브테마를 산출할 키워드 데이터가 부족합니다."

    lines: list[str] = []
    for index, row in enumerate(subtheme_rankings[:5], start=1):
        lines.append(f"{index}. {row['subtheme']} ({row['score']}점)")
        lines.append(
            "대장주: "
            + _theme_stock_label(
                row.get("leader"),
                row.get("leader_grade"),
                row.get("leader_score"),
            )
        )
        stock_details = row.get("stock_details") or []
        related = [
            _theme_stock_label(
                item.get("stock_name"),
                item.get("investment_grade"),
                item.get("investment_score"),
            )
            for item in stock_details[1:5]
        ]
        if not related:
            related = [str(name) for name in (row.get("stocks") or [])[1:5]]
        lines.append("관련 종목: " + (", ".join(related) if related else "-"))
        lines.append(
            "구성: "
            f"종목 {row.get('stock_count', 0)}개, "
            f"PDF 출현 {row.get('pdf_count', 0)}회"
        )
        lines.append("")
    return "\n".join(lines).strip()


def _market_summary_text(
    report_date: date,
    daily_theme: dict[str, Any],
    signals: list[dict[str, Any]],
    analyses_by_stock: dict[str, dict[str, Any]],
) -> str:
    summary = _text(daily_theme.get("market_summary"))
    if summary != "-":
        return summary

    if not signals:
        return f"{report_date.isoformat()} 시장에서는 500억봉 포착 종목 데이터가 부족합니다."

    theme_counts: dict[str, list[str]] = {}
    for row in signals:
        theme = _text(row.get("primary_theme"))
        stock_name = _text(row.get("stock_name"))
        if theme != "-" and stock_name != "-":
            theme_counts.setdefault(theme, []).append(stock_name)
    top_theme, top_theme_stocks = ("개별 테마", [])
    if theme_counts:
        top_theme, top_theme_stocks = max(
            theme_counts.items(),
            key=lambda item: len(item[1]),
        )

    top_trading = sorted(
        signals,
        key=lambda row: _safe_float(row.get("trading_value")) or 0,
        reverse=True,
    )[:3]
    top_trading_names = [
        _text(row.get("stock_name"))
        for row in top_trading
        if _text(row.get("stock_name")) != "-"
    ]
    top_grade_rows = sorted(
        [
            row
            for row in analyses_by_stock.values()
            if _safe_float(row.get("investment_score")) is not None
        ],
        key=lambda row: _safe_float(row.get("investment_score")) or 0,
        reverse=True,
    )[:3]
    top_grade_names = [_text(row.get("stock_name")) for row in top_grade_rows]
    sub_themes = [
        theme
        for theme, _stocks in sorted(
            theme_counts.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )[1:4]
    ]

    parts = [
        f"{report_date.isoformat()} 시장에서는 {top_theme} 테마가 가장 강하게 부각되었습니다.",
    ]
    if top_theme_stocks:
        parts.append(
            f"{', '.join(top_theme_stocks[:5])} 등 관련 종목이 다수 포착되었습니다."
        )
    if sub_themes:
        parts.append(f"{', '.join(sub_themes)} 테마도 함께 관찰되었습니다.")
    if top_trading_names:
        parts.append(
            f"거래대금 기준으로는 {', '.join(top_trading_names)}가 상위권을 차지했습니다."
        )
    if top_grade_names:
        parts.append(
            f"투자등급 점수 기준 상위 종목은 {', '.join(top_grade_names)}입니다."
        )
    return " ".join(parts)


def _investment_notice_text() -> str:
    return (
        "본 리포트는 뉴스, 지식맵, 과거 패턴통계를 종합한 참고 자료입니다. "
        "투자 판단 전 공시, 실적, 수급, 시장 변동성을 함께 확인해야 하며 "
        "매수·매도 추천을 의미하지 않습니다."
    )


def _investment_detail(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _investment_section_text(analysis: dict[str, Any]) -> str:
    grade = _text(analysis.get("investment_grade"))
    score = _safe_float(analysis.get("investment_score"))
    detail = _investment_detail(analysis.get("investment_grade_detail"))
    breakdown = detail.get("score_breakdown") or {}
    reasons = detail.get("grade_reasons") or []
    score_text = "-" if score is None else f"{score:.0f}점"

    lines = [
        f"[{grade}] {score_text}",
        "점수 구성",
        (
            f"패턴 {breakdown.get('pattern', 0)}점 · "
            f"지식맵 {breakdown.get('knowledge', 0)}점 · "
            f"뉴스 {breakdown.get('news', 0)}점"
        ),
    ]
    if reasons:
        lines.append("주요 이유")
        lines.extend(f"- {reason}" for reason in reasons[:4])
    return "\n".join(lines)


def _pending_analysis_text(report_date: date, stock_name: str) -> str:
    return "\n".join(
        [
            "AI 종목 분석이 아직 생성되지 않았습니다.",
            "다음 명령으로 보완 가능:",
            f"python main.py analyze-stock --date {report_date.isoformat()} --stock-name {stock_name}",
        ]
    )


def _top_pick_text(
    daily_theme: dict[str, Any],
    analyses: list[dict[str, Any]] | None = None,
    theme_rankings: list[dict[str, Any]] | None = None,
) -> str:
    analyses = analyses or []
    theme_priority: dict[str, int] = {}
    theme_role_by_stock: dict[str, str] = {}
    for priority, theme_row in enumerate((theme_rankings or [])[:2], start=1):
        weight = 3 - priority
        theme_name = _text(theme_row.get("theme"))
        stock_names = list(theme_row.get("stocks") or [])
        if not stock_names:
            stock_names = [theme_row.get("leader")]
            stock_names.extend(theme_row.get("followers") or [])
        for stock_name in stock_names:
            if stock_name:
                theme_priority[str(stock_name)] = max(
                    theme_priority.get(str(stock_name), 0),
                    weight,
                )
        leader = theme_row.get("leader")
        if leader:
            theme_role_by_stock[str(leader)] = f"{theme_name} {priority}위 테마 대장주"
        for follower in theme_row.get("followers") or []:
            if follower:
                theme_role_by_stock[str(follower)] = (
                    f"{theme_name} {priority}위 테마 후속주"
                )

    ranked_rows = []
    for analysis in analyses:
        investment_score = _safe_float(analysis.get("investment_score"))
        confidence_score = _safe_float(analysis.get("confidence_score")) or 0
        pattern_stats = _pattern_stats_from_analysis(analysis)
        day5_avg_return = _safe_float(pattern_stats.get("day5_avg_return"))
        day5_win_rate = _safe_float(pattern_stats.get("day5_win_rate"))
        signal_count = int(pattern_stats.get("signal_count") or 0)
        stock_name = _text(analysis.get("stock_name"))
        grade = _text(analysis.get("investment_grade"))
        detail = _investment_detail(analysis.get("investment_grade_detail"))
        breakdown = detail.get("score_breakdown") or {}
        news_score = int(breakdown.get("news") or 0)
        if investment_score is None:
            continue
        if grade == "D":
            continue
        ranked_rows.append(
            (
                theme_priority.get(stock_name, 0),
                investment_score,
                confidence_score,
                day5_avg_return if day5_avg_return is not None else -9999,
                signal_count,
                day5_avg_return,
                day5_win_rate,
                news_score,
                analysis,
            )
        )

    if ranked_rows:
        def passes_filter(row: tuple[Any, ...], stage: int) -> bool:
            day5_avg_return = row[5]
            day5_win_rate = row[6]
            news_score = row[7]
            if stage <= 0 and news_score == 0:
                return False
            if stage <= 1 and day5_win_rate is not None and day5_win_rate < 45:
                return False
            if stage <= 2 and day5_avg_return is not None and day5_avg_return < 0:
                return False
            return True

        sorted_rows = sorted(
            ranked_rows,
            key=lambda row: row[:5],
            reverse=True,
        )
        selected_rows: list[tuple[Any, ...]] = []
        selected_stocks: set[str] = set()
        for stage in range(4):
            for row in sorted_rows:
                analysis = row[-1]
                stock_name = _text(analysis.get("stock_name"))
                if stock_name in selected_stocks:
                    continue
                if not passes_filter(row, stage):
                    continue
                selected_rows.append(row)
                selected_stocks.add(stock_name)
                if len(selected_rows) >= 3:
                    break
            if len(selected_rows) >= 3:
                break

        lines = []
        for index, row in enumerate(selected_rows[:3], start=1):
            (
                _theme_priority,
                investment_score,
                _confidence,
                _day5,
                _signals,
                day5_avg_return,
                day5_win_rate,
                _news_score,
                analysis,
            ) = row
            detail = _investment_detail(analysis.get("investment_grade_detail"))
            reasons = detail.get("grade_reasons") or []
            breakdown = detail.get("score_breakdown") or {}
            grade = _text(analysis.get("investment_grade"))
            stock_name = _text(analysis.get("stock_name"))
            lines.append(f"{index}. [{grade}] {stock_name} / {investment_score:.0f}점")
            display_reasons = []
            if stock_name in theme_role_by_stock:
                display_reasons.append(theme_role_by_stock[stock_name])
            if day5_avg_return is not None:
                display_reasons.append(
                    f"D+5 평균 수익률 {day5_avg_return:+.2f}%"
                )
            if day5_win_rate is not None:
                display_reasons.append(f"D+5 상승확률 {day5_win_rate:.1f}%")
            display_reasons.extend(list(reasons[:3]))
            if grade == "C" or int(breakdown.get("news") or 0) <= 10:
                display_reasons.append("뉴스 모멘텀 제한으로 등급 상단이 제한")
            if display_reasons:
                deduped_reasons = list(dict.fromkeys(display_reasons))
                lines.append("주요 이유:")
                lines.extend(f"- {reason}" for reason in deduped_reasons[:4])
            lines.append("")
        return "\n".join(lines).strip()

    if analyses:
        return "투자등급 데이터가 없습니다. analyze-signal-stocks 또는 backfill-investment-grade 실행이 필요합니다."

    value = _text(daily_theme.get("top_picks"))
    if value == "-":
        return "-"
    lines = []
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            name, point = stripped.split(":", 1)
            lines.append(f"{name.strip()}: {point.strip()}")
        else:
            lines.append(stripped)
    return "\n".join(lines[:3]) or value


def _load_daily_theme_analysis(report_date: date) -> dict[str, Any] | None:
    sql = """
        SELECT
            report_date,
            market_summary,
            strong_themes,
            theme_rankings,
            key_issues,
            market_drivers,
            top_picks,
            risk_points,
            tomorrow_checkpoints,
            confidence_score,
            source_stock_count,
            source_news_count
        FROM daily_theme_analysis
        WHERE report_date = %(report_date)s
        LIMIT 1
    """
    return _fetch_one(sql, {"report_date": report_date})


def _load_signal_events(report_date: date) -> list[dict[str, Any]]:
    sql = """
        SELECT
            se.stock_code,
            sm.stock_name,
            se.trading_value,
            se.close_price,
            se.volume,
            COALESCE(sp.primary_theme, '-') AS primary_theme
        FROM signal_event se
        JOIN stock_master sm
            ON sm.stock_code = se.stock_code
        LEFT JOIN stock_profile sp
            ON sp.stock_name = sm.stock_name
        WHERE se.signal_date = %(report_date)s
        ORDER BY se.trading_value DESC NULLS LAST, sm.stock_name
    """
    return _fetch_all(sql, {"report_date": report_date})


def _load_stock_analyses(report_date: date) -> list[dict[str, Any]]:
    sql = """
        SELECT DISTINCT ON (a.stock_name)
            a.stock_name,
            a.summary,
            a.key_issues,
            a.positive_points,
            a.risk_points,
            a.theme_points,
            a.tomorrow_checkpoints,
            a.knowledge_points,
            a.pattern_points,
            a.investment_score,
            a.investment_grade,
            a.investment_grade_detail,
            a.sentiment,
            a.confidence_score,
            sps.signal_count AS pattern_signal_count,
            sps.source_signal_count,
            sps.source_pdf_count,
            sps.next_day_win_rate,
            sps.next_day_avg_return,
            sps.day3_win_rate,
            sps.day3_avg_return,
            sps.day5_win_rate,
            sps.day5_avg_return,
            sps.max_return_5d,
            sps.min_return_5d
        FROM stock_analysis a
        LEFT JOIN stock_pattern_stats sps
            ON sps.stock_name = a.stock_name
        WHERE a.analysis_date::date = %(report_date)s
        ORDER BY a.stock_name, a.analysis_date DESC, a.id DESC
    """
    return _fetch_all(sql, {"report_date": report_date})


def _load_relevant_news(report_date: date, limit: int = 5) -> list[dict[str, Any]]:
    sql = """
        SELECT
            n.stock_name,
            n.title,
            n.description,
            n.ai_summary,
            n.source,
            n.published_at,
            n.relevance_score,
            n.link
        FROM news_article n
        WHERE n.is_relevant = TRUE
            AND (
                n.published_at::date = %(report_date)s
                OR n.created_at::date = %(report_date)s
            )
        ORDER BY n.relevance_score DESC NULLS LAST,
            n.published_at DESC NULLS LAST,
            n.id DESC
        LIMIT %(limit)s
    """
    return _fetch_all(sql, {"report_date": report_date, "limit": limit})


def get_stock_news_for_report(
    stock_name: str,
    report_date: date,
    limit: int = 3,
) -> list[dict[str, Any]]:
    date_sql = """
        SELECT
            n.stock_name,
            n.title,
            n.description,
            n.ai_summary,
            n.source,
            n.published_at,
            n.relevance_score,
            n.link
        FROM news_article n
        WHERE n.stock_name = %(stock_name)s
            AND n.is_relevant = TRUE
            AND (
                n.published_at::date = %(report_date)s
                OR n.created_at::date = %(report_date)s
            )
        ORDER BY n.relevance_score DESC NULLS LAST,
            n.published_at DESC NULLS LAST,
            n.id DESC
        LIMIT %(limit)s
    """
    rows = _fetch_all(
        date_sql,
        {"stock_name": stock_name, "report_date": report_date, "limit": limit},
    )
    if rows:
        return rows

    fallback_sql = """
        SELECT
            n.stock_name,
            n.title,
            n.description,
            n.ai_summary,
            n.source,
            n.published_at,
            n.relevance_score,
            n.link
        FROM news_article n
        WHERE n.stock_name = %(stock_name)s
            AND n.is_relevant = TRUE
        ORDER BY n.relevance_score DESC NULLS LAST,
            n.published_at DESC NULLS LAST,
            n.id DESC
        LIMIT %(limit)s
    """
    return _fetch_all(fallback_sql, {"stock_name": stock_name, "limit": limit})


def _build_signal_table(
    rows: list[dict[str, Any]],
    analyses_by_stock: dict[str, dict[str, Any]],
    styles: dict[str, Any],
) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table_rows = [
        [
            _paragraph("순위", styles["table_header"]),
            _paragraph("등급", styles["table_header"]),
            _paragraph("종목명", styles["table_header"]),
            _paragraph("투자점수", styles["table_header"]),
            _paragraph("거래대금", styles["table_header"]),
            _paragraph("대표테마", styles["table_header"]),
            _paragraph("D+5 평균", styles["table_header"]),
        ]
    ]
    for rank, row in enumerate(rows, start=1):
        analysis = analyses_by_stock.get(_text(row.get("stock_name")), {})
        investment_score = _safe_float(analysis.get("investment_score"))
        pattern_stats = _pattern_stats_from_analysis(analysis)
        table_rows.append(
            [
                _paragraph(rank, styles["small"]),
                _paragraph(analysis.get("investment_grade"), styles["small"]),
                _paragraph(row.get("stock_name"), styles["small"]),
                _paragraph(
                    "-" if investment_score is None else f"{investment_score:.0f}",
                    styles["small"],
                ),
                _paragraph(
                    _format_trading_value_eok(row.get("trading_value")),
                    styles["small"],
                ),
                _paragraph(row.get("primary_theme"), styles["small"]),
                _paragraph(
                    _format_pattern_pct(
                        pattern_stats.get("day5_avg_return"),
                        show_sign=True,
                    ),
                    styles["small"],
                ),
            ]
        )

    table = Table(
        table_rows,
        colWidths=[24, 30, 72, 44, 62, 190, 48],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _build_news_table(rows: list[dict[str, Any]], styles: dict[str, Any]) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table_rows = [
        [
            _paragraph("번호", styles["table_header"]),
            _paragraph("제목", styles["table_header"]),
            _paragraph("요약", styles["table_header"]),
            _paragraph("발행시각", styles["table_header"]),
            _paragraph("점수", styles["table_header"]),
            _paragraph("출처", styles["table_header"]),
            _paragraph("원문", styles["table_header"]),
        ]
    ]
    for index, row in enumerate(rows, start=1):
        source = _text(row.get("source"))
        table_rows.append(
            [
                _paragraph(index, styles["small"]),
                _paragraph(row.get("title"), styles["small"]),
                _paragraph(_news_summary_text(row), styles["small"]),
                _paragraph(row.get("published_at"), styles["small"]),
                _paragraph(_format_score(row.get("relevance_score")), styles["small"]),
                _paragraph(source, styles["small"]),
                _link_paragraph(row.get("link"), "원문", styles["small"]),
            ]
        )

    table = Table(table_rows, colWidths=[25, 115, 95, 75, 35, 60, 30], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _add_news_cards(story: list[Any], rows: list[dict[str, Any]], styles: dict[str, Any]) -> None:
    from reportlab.platypus import Paragraph, Spacer

    for index, row in enumerate(rows, start=1):
        title = _truncate_with_ellipsis(_text(row.get("title")), 70)
        source = _text(row.get("source"))
        published_at = _text(row.get("published_at"))
        score = _format_score(row.get("relevance_score"))
        story.append(Paragraph(f"{index}. {title}", styles["section"]))
        story.append(_paragraph(_news_summary_text(row), styles["body"]))
        story.append(
            _paragraph(
                f"{published_at} / 점수 {score} / {source}",
                styles["small"],
            )
        )
        story.append(_link_paragraph(row.get("link"), "원문", styles["small"]))
        story.append(Spacer(1, 8))


def _add_separator(story: list[Any]) -> None:
    from reportlab.lib import colors
    from reportlab.platypus import HRFlowable, Spacer

    story.append(Spacer(1, 12))
    story.append(
        HRFlowable(
            width="100%",
            thickness=0.7,
            color=colors.HexColor("#BDBDBD"),
            spaceBefore=6,
            spaceAfter=12,
        )
    )


def generate_daily_report(report_date: date) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    font_name, bold_font_name = _register_korean_font()
    print(f"PDF font regular: {font_name}")
    print(f"PDF font bold: {bold_font_name}")
    styles = _build_styles(font_name, bold_font_name)

    output_dir = REPORT_ROOT / report_date.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"daily_report_{report_date.isoformat()}.pdf"

    daily_theme = _load_daily_theme_analysis(report_date) or {}
    signals = _load_signal_events(report_date)
    analyses = _load_stock_analyses(report_date)
    theme_rankings = build_theme_rankings(report_date)
    subtheme_rankings = build_subtheme_rankings(report_date)
    analyses_by_stock = {row["stock_name"]: row for row in analyses}
    signal_analyses = [
        analyses_by_stock[row["stock_name"]]
        for row in signals
        if row.get("stock_name") in analyses_by_stock
    ]
    news = _load_relevant_news(report_date, limit=5)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"주도주 AI 투자 리포트 {report_date.isoformat()}",
    )
    story: list[Any] = []

    story.append(Paragraph("주도주 AI 투자 리포트", styles["title"]))
    story.append(_paragraph(f"날짜: {report_date.isoformat()}", styles["body"]))
    story.append(_paragraph(f"생성시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["body"]))
    story.append(Spacer(1, 24))

    story.append(Paragraph("시장 요약", styles["heading"]))
    _add_report_section(
        story,
        "시장 요약",
        _market_summary_text(report_date, daily_theme, signals, analyses_by_stock),
        styles,
    )
    _add_report_section(
        story,
        "시장 강도",
        _market_strength_text_from_inputs(daily_theme, signals, signal_analyses),
        styles,
    )
    _add_report_section(
        story,
        "오늘의 주도 테마",
        _leading_theme_text_from_inputs(daily_theme, signals),
        styles,
    )
    _add_report_section(
        story,
        "주도 테마 랭킹",
        _theme_ranking_text(theme_rankings),
        styles,
    )
    _add_report_section(
        story,
        "주도 서브테마",
        _subtheme_ranking_text(subtheme_rankings),
        styles,
    )
    _add_report_section(
        story,
        "TOP PICK",
        _top_pick_text(daily_theme, signal_analyses, theme_rankings),
        styles,
    )
    _add_report_section(story, "투자 유의사항", _investment_notice_text(), styles)
    story.append(PageBreak())

    if signals:
        story.append(
            KeepTogether(
                [
                    Paragraph("500억봉 종목 요약", styles["heading"]),
                    _build_signal_table(signals, analyses_by_stock, styles),
                ]
            )
        )
    else:
        story.append(Paragraph("500억봉 종목 요약", styles["heading"]))
        story.append(_paragraph("해당 날짜의 signal_event 데이터가 없습니다.", styles["body"]))
    story.append(Spacer(1, 16))

    story.append(Paragraph("종목별 상세", styles["heading"]))
    if signals:
        for signal in signals:
            _add_separator(story)
            stock_name = _text(signal.get("stock_name"))
            analysis = analyses_by_stock.get(stock_name)
            pattern_stats = _pattern_stats_from_analysis(analysis)
            if int(pattern_stats.get("signal_count") or 0) <= 0:
                pattern_stats = get_stock_pattern_stats(stock_name)
            title = f"{stock_name} / 대표테마: {_text(signal.get('primary_theme'))}"
            story.append(Paragraph(title, styles["stock_heading"]))

            if analysis is None:
                _add_report_section(story, "투자등급", "분석 전", styles)
                _add_report_section(
                    story,
                    "지식맵 해석",
                    _knowledge_map_text(stock_name, signal, {}, pattern_stats),
                    styles,
                )
                _add_report_section(
                    story,
                    "과거 패턴 통계",
                    _pattern_stats_text(pattern_stats, None),
                    styles,
                )
                _add_report_section(
                    story,
                    "분석 상태",
                    _pending_analysis_text(report_date, stock_name),
                    styles,
                )
            else:
                for column, label in (
                    ("summary", "한줄 요약"),
                    ("investment_grade", "투자등급"),
                    ("knowledge_points", "지식맵 해석"),
                    ("pattern_points", "과거 패턴 통계"),
                    ("positive_points", "긍정 요인"),
                    ("risk_points", "리스크"),
                    ("tomorrow_checkpoints", "내일 체크"),
                ):
                    value = analysis.get(column)
                    if column == "investment_grade":
                        value = _investment_section_text(analysis)
                    if column == "knowledge_points":
                        value = _knowledge_map_text(
                            stock_name,
                            signal,
                            analysis,
                            pattern_stats,
                        )
                    if column == "pattern_points":
                        value = _pattern_stats_text(pattern_stats, value)
                    _add_report_section(story, label, value, styles)

            story.append(Paragraph("관련 뉴스", styles["heading"]))
            stock_news = get_stock_news_for_report(
                stock_name=stock_name,
                report_date=report_date,
                limit=3,
            )
            if stock_news:
                _add_news_cards(story, stock_news, styles)
            else:
                story.append(_paragraph("관련 뉴스 없음", styles["body"]))
            story.append(Spacer(1, 18))
    else:
        story.append(_paragraph("해당 날짜의 signal_event 데이터가 없습니다.", styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("전체 주요 뉴스", styles["heading"]))
    if news:
        _add_news_cards(story, news, styles)
    else:
        story.append(_paragraph("관련 뉴스가 없습니다.", styles["body"]))

    doc.build(story)
    return output_path
