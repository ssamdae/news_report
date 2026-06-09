from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from database.db import get_connection
from database.pattern_repository import get_stock_pattern_stats


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

    lines = [
        f"발생횟수: {signal_count}회",
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
    try:
        score = float(daily_theme.get("confidence_score") or 0)
    except (TypeError, ValueError):
        score = 0

    if score >= 80:
        stars = "★★★★★"
    elif score >= 65:
        stars = "★★★★☆"
    elif score >= 50:
        stars = "★★★☆☆"
    else:
        stars = "★★☆☆☆"

    strong_themes = _text(daily_theme.get("strong_themes"))
    if strong_themes == "-":
        return f"{stars}"
    return f"{stars}\n{strong_themes}"


def _top_pick_text(daily_theme: dict[str, Any]) -> str:
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
        SELECT
            a.stock_name,
            a.summary,
            a.key_issues,
            a.positive_points,
            a.risk_points,
            a.theme_points,
            a.tomorrow_checkpoints,
            a.knowledge_points,
            a.pattern_points,
            a.sentiment,
            a.confidence_score
        FROM stock_analysis a
        WHERE a.report_date = %(report_date)s
        ORDER BY a.stock_name
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


def _build_signal_table(rows: list[dict[str, Any]], styles: dict[str, Any]) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table_rows = [
        [
            _paragraph("순위", styles["table_header"]),
            _paragraph("종목명", styles["table_header"]),
            _paragraph("거래대금", styles["table_header"]),
            _paragraph("대표테마", styles["table_header"]),
        ]
    ]
    for rank, row in enumerate(rows, start=1):
        table_rows.append(
            [
                _paragraph(rank, styles["small"]),
                _paragraph(row.get("stock_name"), styles["small"]),
                _paragraph(_format_number(row.get("trading_value")), styles["small"]),
                _paragraph(row.get("primary_theme"), styles["small"]),
            ]
        )

    table = Table(table_rows, colWidths=[30, 115, 95, 230], repeatRows=1)
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
    analyses_by_stock = {row["stock_name"]: row for row in analyses}
    news = _load_relevant_news(report_date, limit=5)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"주도주 AI 분석 리포트 {report_date.isoformat()}",
    )
    story: list[Any] = []

    story.append(Paragraph("주도주 AI 분석 리포트", styles["title"]))
    story.append(_paragraph(f"날짜: {report_date.isoformat()}", styles["body"]))
    story.append(_paragraph(f"생성시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["body"]))
    story.append(Spacer(1, 24))

    story.append(Paragraph("시장 요약", styles["heading"]))
    _add_report_section(story, "시장 요약", daily_theme.get("market_summary"), styles)
    _add_report_section(story, "시장 강도", _market_strength_text(daily_theme), styles)
    _add_report_section(story, "TOP PICK", _top_pick_text(daily_theme), styles)
    story.append(PageBreak())

    if signals:
        story.append(
            KeepTogether(
                [
                    Paragraph("500억봉 종목 요약", styles["heading"]),
                    _build_signal_table(signals, styles),
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
            pattern_stats = get_stock_pattern_stats(stock_name)
            title = f"{stock_name} / 대표테마: {_text(signal.get('primary_theme'))}"
            story.append(Paragraph(title, styles["stock_heading"]))

            if analysis is None:
                story.append(_paragraph("분석 데이터 없음", styles["body"]))
            else:
                for column, label in (
                    ("summary", "한줄 요약"),
                    ("knowledge_points", "지식맵 해석"),
                    ("pattern_points", "과거 패턴 통계"),
                    ("positive_points", "긍정 요인"),
                    ("risk_points", "리스크"),
                    ("tomorrow_checkpoints", "내일 체크"),
                ):
                    value = analysis.get(column)
                    if column == "knowledge_points":
                        value = _knowledge_points_text(value)
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
