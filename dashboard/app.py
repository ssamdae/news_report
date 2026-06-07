from datetime import date

import pandas as pd
import streamlit as st

from database.db import get_connection


SIGNAL_NAME = "500억봉"


st.set_page_config(page_title="500억봉 대시보드", layout="wide")


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(query, connection, params=params)


def format_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.0f}"


def load_signal_events(signal_date: date) -> pd.DataFrame:
    query = """
        SELECT
            e.signal_date,
            e.stock_code,
            m.stock_name,
            m.market,
            e.signal_name,
            e.condition_version,
            e.trading_value,
            e.close_price,
            e.volume,
            e.created_at
        FROM signal_event e
        JOIN stock_master m
            ON m.stock_code = e.stock_code
        WHERE e.signal_date = %(signal_date)s
            AND e.signal_name = %(signal_name)s
        ORDER BY e.trading_value DESC NULLS LAST, e.stock_code
    """
    return read_sql(query, {"signal_date": signal_date, "signal_name": SIGNAL_NAME})


def load_news_by_date(news_date: date) -> pd.DataFrame:
    query = """
        SELECT
            stock_name,
            title,
            source,
            keyword,
            published_at,
            link
        FROM news_article
        WHERE created_at::date = %(news_date)s
        ORDER BY published_at DESC NULLS LAST, created_at DESC
    """
    return read_sql(query, {"news_date": news_date})


def search_stocks(keyword: str) -> pd.DataFrame:
    query = """
        SELECT
            stock_code,
            stock_name,
            market
        FROM stock_master
        WHERE stock_name ILIKE %(keyword)s
            OR stock_code ILIKE %(keyword)s
        ORDER BY stock_name
        LIMIT 50
    """
    return read_sql(query, {"keyword": f"%{keyword}%"})


def load_stock_detail(stock_code: str) -> pd.DataFrame:
    query = """
        SELECT
            e.signal_date,
            e.stock_code,
            m.stock_name,
            m.market,
            d.open_price,
            d.high_price,
            d.low_price,
            d.close_price,
            d.prev_close_price,
            d.volume,
            d.trading_value,
            e.condition_version,
            e.created_at
        FROM signal_event e
        JOIN stock_master m
            ON m.stock_code = e.stock_code
        LEFT JOIN daily_price d
            ON d.stock_code = e.stock_code
            AND d.trade_date = e.signal_date
        WHERE e.stock_code = %(stock_code)s
            AND e.signal_name = %(signal_name)s
        ORDER BY e.signal_date DESC
    """
    return read_sql(query, {"stock_code": stock_code, "signal_name": SIGNAL_NAME})


def load_stock_profile(stock_name: str) -> pd.DataFrame:
    query = """
        SELECT
            stock_name,
            primary_theme,
            secondary_theme,
            related_themes,
            theme_count,
            total_hit_count,
            first_seen_date,
            last_seen_date
        FROM stock_profile
        WHERE stock_name = %(stock_name)s
    """
    return read_sql(query, {"stock_name": stock_name})


def load_news_by_stock(stock_code: str) -> pd.DataFrame:
    query = """
        SELECT
            stock_name,
            title,
            source,
            keyword,
            published_at,
            link
        FROM news_article
        WHERE stock_code = %(stock_code)s
        ORDER BY published_at DESC NULLS LAST, created_at DESC
    """
    return read_sql(query, {"stock_code": stock_code})


def load_analysis_stock_names() -> pd.DataFrame:
    query = """
        SELECT DISTINCT stock_name
        FROM stock_analysis
        ORDER BY stock_name
    """
    return read_sql(query)


def load_analysis_by_report_date(report_date: date) -> pd.DataFrame:
    query = """
        SELECT
            stock_name,
            report_date,
            analysis_date,
            summary,
            sentiment,
            confidence_score,
            source_news_count
        FROM stock_analysis
        WHERE report_date = %(report_date)s
        ORDER BY confidence_score DESC NULLS LAST, stock_name
    """
    return read_sql(query, {"report_date": report_date})


def display_news_table(news: pd.DataFrame) -> None:
    if news.empty:
        st.info("저장된 뉴스가 없습니다.")
        return

    display_news = news.rename(
        columns={
            "stock_name": "종목명",
            "title": "제목",
            "source": "source",
            "keyword": "keyword",
            "published_at": "published_at",
            "link": "link",
        }
    )
    st.dataframe(
        display_news,
        use_container_width=True,
        hide_index=True,
        column_config={
            "link": st.column_config.LinkColumn("link"),
        },
    )


st.title("500억봉 대시보드")

selected_date = st.date_input("날짜 선택", value=date.today())
try:
    signals = load_signal_events(selected_date)
except Exception as error:
    st.error(f"DB 조회 중 오류가 발생했습니다: {error}")
    st.stop()

summary_cols = st.columns(3)
summary_cols[0].metric("조회 날짜", selected_date.isoformat())
summary_cols[1].metric("500억봉 종목 수", f"{len(signals):,}")
summary_cols[2].metric(
    "총 거래대금",
    format_number(signals["trading_value"].sum() if not signals.empty else 0),
)

st.subheader("해당 날짜 500억봉 종목")

if signals.empty:
    st.info("선택한 날짜에 저장된 500억봉 종목이 없습니다.")
else:
    display_signals = signals.rename(
        columns={
            "signal_date": "날짜",
            "stock_code": "종목코드",
            "stock_name": "종목명",
            "market": "시장",
            "signal_name": "신호명",
            "condition_version": "조건버전",
            "trading_value": "거래대금",
            "close_price": "종가",
            "volume": "거래량",
            "created_at": "저장시각",
        }
    )
    st.dataframe(display_signals, use_container_width=True, hide_index=True)

st.subheader("해당 날짜 저장 뉴스")

try:
    date_news = load_news_by_date(selected_date)
except Exception as error:
    st.warning(f"뉴스 조회 중 오류가 발생했습니다: {error}")
else:
    display_news_table(date_news)

st.divider()
st.subheader("종목명 검색")

keyword = st.text_input("종목명 또는 종목코드")
selected_stock_code = None

if keyword.strip():
    try:
        search_results = search_stocks(keyword.strip())
    except Exception as error:
        st.error(f"종목 검색 중 오류가 발생했습니다: {error}")
        st.stop()

    if search_results.empty:
        st.info("검색 결과가 없습니다.")
    else:
        options = {
            f"{row.stock_name} ({row.stock_code}, {row.market})": row.stock_code
            for row in search_results.itertuples(index=False)
        }
        selected_label = st.selectbox("종목 선택", options=list(options.keys()))
        selected_stock_code = options[selected_label]

st.subheader("종목 상세 조회")

if selected_stock_code is None:
    st.info("종목을 검색하고 선택하면 상세 이력이 표시됩니다.")
else:
    try:
        detail = load_stock_detail(selected_stock_code)
    except Exception as error:
        st.error(f"종목 상세 조회 중 오류가 발생했습니다: {error}")
        st.stop()

    selected_stock_name = search_results.loc[
        search_results["stock_code"] == selected_stock_code,
        "stock_name",
    ].iloc[0]

    st.subheader("종목 테마 프로필")
    try:
        profile = load_stock_profile(selected_stock_name)
    except Exception as error:
        st.warning(f"종목 테마 프로필 조회 중 오류가 발생했습니다: {error}")
    else:
        if profile.empty:
            st.info("저장된 종목 테마 프로필이 없습니다.")
        else:
            profile_row = profile.iloc[0]
            profile_cols = st.columns(4)
            profile_cols[0].metric("대표 테마", profile_row["primary_theme"] or "-")
            profile_cols[1].metric("보조 테마", profile_row["secondary_theme"] or "-")
            profile_cols[2].metric(
                "총 등장 횟수",
                f"{int(profile_row['total_hit_count']):,}",
            )
            profile_cols[3].metric("테마 수", f"{int(profile_row['theme_count']):,}")

            date_cols = st.columns(2)
            date_cols[0].metric("최초 등장일", str(profile_row["first_seen_date"]))
            date_cols[1].metric("최근 등장일", str(profile_row["last_seen_date"]))
            st.caption(f"연관 테마: {profile_row['related_themes']}")

    if detail.empty:
        st.info("선택한 종목의 500억봉 이력이 없습니다.")
    else:
        latest = detail.iloc[0]
        detail_cols = st.columns(4)
        detail_cols[0].metric("종목명", latest["stock_name"])
        detail_cols[1].metric("종목코드", latest["stock_code"])
        detail_cols[2].metric("시장", latest["market"])
        detail_cols[3].metric("최근 신호일", str(latest["signal_date"]))

        display_detail = detail.rename(
            columns={
                "signal_date": "신호일",
                "stock_code": "종목코드",
                "stock_name": "종목명",
                "market": "시장",
                "open_price": "시가",
                "high_price": "고가",
                "low_price": "저가",
                "close_price": "종가",
                "prev_close_price": "전일종가",
                "volume": "거래량",
                "trading_value": "거래대금",
                "condition_version": "조건버전",
                "created_at": "저장시각",
            }
        )
        st.dataframe(display_detail, use_container_width=True, hide_index=True)

        st.subheader("선택 종목 뉴스")
        try:
            stock_news = load_news_by_stock(selected_stock_code)
        except Exception as error:
            st.warning(f"뉴스 조회 중 오류가 발생했습니다: {error}")
        else:
            display_news_table(stock_news)

st.divider()
st.subheader("AI 분석")

try:
    date_analysis = load_analysis_by_report_date(selected_date)
except Exception as error:
    st.warning(f"선택 날짜 AI 분석 현황 조회 중 오류가 발생했습니다: {error}")
else:
    st.markdown("#### 선택 날짜 분석 현황")
    if date_analysis.empty:
        st.info("선택한 날짜에 저장된 AI 분석 결과가 없습니다.")
    else:
        analysis_summary_cols = st.columns(3)
        analysis_summary_cols[0].metric("분석 완료 종목", f"{len(date_analysis):,}")
        analysis_summary_cols[1].metric(
            "평균 confidence",
            f"{float(date_analysis['confidence_score'].mean()):.2f}",
        )
        analysis_summary_cols[2].metric(
            "사용 뉴스 합계",
            f"{int(date_analysis['source_news_count'].sum()):,}",
        )

        display_date_analysis = date_analysis.rename(
            columns={
                "stock_name": "종목명",
                "report_date": "분석일",
                "analysis_date": "생성시각",
                "summary": "요약",
                "sentiment": "sentiment",
                "confidence_score": "confidence",
                "source_news_count": "뉴스수",
            }
        )
        st.dataframe(
            display_date_analysis,
            use_container_width=True,
            hide_index=True,
        )

try:
    analysis_stocks = load_analysis_stock_names()
except Exception as error:
    st.warning(f"AI 분석 종목 목록 조회 중 오류가 발생했습니다: {error}")
    analysis_stocks = pd.DataFrame(columns=["stock_name"])

analysis_options = ["직접 입력"]
if not analysis_stocks.empty:
    analysis_options.extend(analysis_stocks["stock_name"].dropna().astype(str).tolist())

analysis_cols = st.columns([2, 2])
analysis_choice = analysis_cols[0].selectbox("분석 종목 선택", analysis_options)
manual_stock_name = analysis_cols[1].text_input("종목명 직접 입력")

analysis_stock_name = (
    manual_stock_name.strip()
    if manual_stock_name.strip()
    else (analysis_choice if analysis_choice != "직접 입력" else "")
)
analysis_date = st.date_input("분석일 선택", value=selected_date, key="analysis_date")

if not analysis_stock_name:
    st.info("AI 분석을 조회할 종목명을 선택하거나 입력하세요.")
else:
    from database.news_repository import (
        get_relevant_news_for_display,
        get_stock_analysis,
    )

    try:
        analysis = get_stock_analysis(
            stock_name=analysis_stock_name,
            report_date=analysis_date,
        )
    except Exception as error:
        st.warning(f"AI 분석 조회 중 오류가 발생했습니다: {error}")
        analysis = pd.DataFrame()

    if analysis.empty:
        st.info(
            "해당 종목의 분석 결과가 없습니다. analyze-stock 명령을 먼저 실행하세요."
        )
    else:
        analysis_row = analysis.iloc[0]
        st.markdown(f"#### {analysis_row['stock_name']} AI 분석")

        metric_cols = st.columns(4)
        metric_cols[0].metric("분석일", str(analysis_row["report_date"]))
        metric_cols[1].metric("sentiment", analysis_row["sentiment"] or "-")
        metric_cols[2].metric(
            "confidence",
            (
                f"{float(analysis_row['confidence_score']):.2f}"
                if pd.notna(analysis_row["confidence_score"])
                else "-"
            ),
        )
        metric_cols[3].metric(
            "사용 뉴스 수",
            f"{int(analysis_row['source_news_count']):,}",
        )

        st.markdown("##### 한줄 요약")
        st.write(analysis_row["summary"] or "-")

        text_sections = [
            ("핵심 이슈", "key_issues"),
            ("상승/관심 요인", "positive_points"),
            ("리스크 요인", "risk_points"),
            ("관련 테마", "theme_points"),
            ("내일 체크포인트", "tomorrow_checkpoints"),
        ]
        for label, column in text_sections:
            st.markdown(f"##### {label}")
            st.write(analysis_row[column] or "-")

    st.markdown("#### 관련 뉴스")
    try:
        relevant_news = get_relevant_news_for_display(
            stock_name=analysis_stock_name,
            limit=30,
        )
    except Exception as error:
        st.warning(f"관련 뉴스 조회 중 오류가 발생했습니다: {error}")
    else:
        if relevant_news.empty:
            st.info("관련 뉴스가 없습니다.")
        else:
            display_relevant_news = relevant_news.rename(
                columns={
                    "title": "제목",
                    "search_query": "검색쿼리",
                    "relevance_score": "관련성점수",
                    "published_at": "발행시각",
                    "link": "link",
                }
            )
            st.dataframe(
                display_relevant_news,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "link": st.column_config.LinkColumn("link"),
                },
            )
