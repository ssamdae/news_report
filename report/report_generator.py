from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from database.db import get_connection


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


def _register_korean_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    font_candidates = [
        ("AppleGothic", "/System/Library/Fonts/AppleGothic.ttf"),
        ("NanumGothic", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        ("NotoSansCJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for font_name, font_path in font_candidates:
        path = Path(font_path)
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
            return font_name
        except Exception:
            continue

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
        return "HYSMyeongJo-Medium"
    except Exception:
        return "Helvetica"


def _build_styles(font_name: str) -> dict[str, Any]:
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "KoreanTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=24,
            leading=32,
            spaceAfter=18,
            alignment=1,
        ),
        "heading": ParagraphStyle(
            "KoreanHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=15,
            leading=20,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "KoreanSection",
            parent=styles["Heading3"],
            fontName=font_name,
            fontSize=12,
            leading=16,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "KoreanBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=14,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "KoreanSmall",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8,
            leading=11,
            spaceAfter=4,
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


def _load_daily_theme_analysis(report_date: date) -> dict[str, Any] | None:
    sql = """
        SELECT
            report_date,
            market_summary,
            strong_themes,
            theme_rankings,
            key_issues,
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
    limit: int = 5,
) -> list[dict[str, Any]]:
    date_sql = """
        SELECT
            n.stock_name,
            n.title,
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
            _paragraph("순위", styles["small"]),
            _paragraph("종목명", styles["small"]),
            _paragraph("거래대금", styles["small"]),
            _paragraph("대표테마", styles["small"]),
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

    table = Table(table_rows, colWidths=[35, 120, 105, 210], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _build_news_table(rows: list[dict[str, Any]], styles: dict[str, Any]) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table_rows = [
        [
            _paragraph("번호", styles["small"]),
            _paragraph("title", styles["small"]),
            _paragraph("published_at", styles["small"]),
            _paragraph("score", styles["small"]),
            _paragraph("출처", styles["small"]),
            _paragraph("원문", styles["small"]),
        ]
    ]
    for index, row in enumerate(rows, start=1):
        source = _text(row.get("source"))
        table_rows.append(
            [
                _paragraph(index, styles["small"]),
                _paragraph(row.get("title"), styles["small"]),
                _paragraph(row.get("published_at"), styles["small"]),
                _paragraph(row.get("relevance_score"), styles["small"]),
                _paragraph(source, styles["small"]),
                _link_paragraph(row.get("link"), "원문", styles["small"]),
            ]
        )

    table = Table(table_rows, colWidths=[30, 205, 85, 40, 75, 35], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _add_separator(story: list[Any]) -> None:
    from reportlab.lib import colors
    from reportlab.platypus import HRFlowable, Spacer

    story.append(Spacer(1, 6))
    story.append(
        HRFlowable(
            width="100%",
            thickness=0.5,
            color=colors.HexColor("#BDBDBD"),
            spaceBefore=4,
            spaceAfter=8,
        )
    )


def generate_daily_report(report_date: date) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    font_name = _register_korean_font()
    styles = _build_styles(font_name)

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
    _add_report_section(story, "강세 테마", daily_theme.get("strong_themes"), styles)
    _add_report_section(story, "테마 순위", daily_theme.get("theme_rankings"), styles)
    _add_report_section(story, "주요 이슈", daily_theme.get("key_issues"), styles)
    _add_report_section(story, "리스크 요인", daily_theme.get("risk_points"), styles)
    _add_report_section(
        story,
        "내일 체크포인트",
        daily_theme.get("tomorrow_checkpoints"),
        styles,
    )

    story.append(Paragraph("500억봉 종목 요약", styles["heading"]))
    if signals:
        story.append(_build_signal_table(signals, styles))
    else:
        story.append(_paragraph("해당 날짜의 signal_event 데이터가 없습니다.", styles["body"]))
    story.append(PageBreak())

    story.append(Paragraph("종목별 상세", styles["heading"]))
    if signals:
        for signal in signals:
            _add_separator(story)
            stock_name = _text(signal.get("stock_name"))
            analysis = analyses_by_stock.get(stock_name)
            title = f"{stock_name} / 대표테마: {_text(signal.get('primary_theme'))}"
            story.append(Paragraph(title, styles["heading"]))

            if analysis is None:
                story.append(_paragraph("분석 데이터 없음", styles["body"]))
            else:
                for column, label in (
                    ("summary", "요약"),
                    ("key_issues", "핵심 이슈"),
                    ("positive_points", "긍정 요인"),
                    ("risk_points", "리스크 요인"),
                    ("theme_points", "관련 테마"),
                    ("tomorrow_checkpoints", "내일 체크포인트"),
                    ("sentiment", "분위기"),
                    ("confidence_score", "신뢰도"),
                ):
                    _add_report_section(story, label, analysis.get(column), styles)

            story.append(Paragraph("관련 뉴스", styles["heading"]))
            stock_news = get_stock_news_for_report(
                stock_name=stock_name,
                report_date=report_date,
                limit=5,
            )
            if stock_news:
                story.append(_build_news_table(stock_news, styles))
            else:
                story.append(_paragraph("관련 뉴스 없음", styles["body"]))
            story.append(Spacer(1, 10))
    else:
        story.append(_paragraph("해당 날짜의 signal_event 데이터가 없습니다.", styles["body"]))

    story.append(Paragraph("전체 관련 뉴스 TOP 5", styles["heading"]))
    if news:
        story.append(_build_news_table(news, styles))
    else:
        story.append(_paragraph("관련 뉴스가 없습니다.", styles["body"]))

    doc.build(story)
    return output_path
