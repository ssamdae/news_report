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
