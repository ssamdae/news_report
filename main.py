from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from pathlib import Path

from database.db import test_connection


def _parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _parse_float_list(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def run(target_date: date, limit_stocks: int | None = None) -> None:
    from collector.news_collector import collect_news_for_signals
    from collector.stock_collector import collect_daily_stocks
    from database.news_repository import (
        apply_news_relevance_scores,
        load_active_stock_keywords,
        save_news_articles,
    )
    from database.signal_event_repository import save_signal_events
    from database.stock_repository import save_daily_prices, save_stock_master
    from filter.signal_filter import filter_500eok_signal

    print(f"주가 수집 시작: {target_date.isoformat()}")
    if limit_stocks is not None:
        print(f"주가 수집 제한: 상위 {limit_stocks}개 종목")
    stock_df = collect_daily_stocks(target_date, limit_stocks=limit_stocks)
    print(f"주가 수집 완료: {len(stock_df)}건")

    signal_df = filter_500eok_signal(stock_df)
    print(f"500억봉 탐지 완료: {len(signal_df)}건")

    stock_count = save_stock_master(stock_df)
    daily_price_count = save_daily_prices(stock_df)
    signal_count = save_signal_events(signal_df, signal_date=target_date)

    print(f"stock_master 저장 완료: {stock_count}건")
    print(f"daily_price 저장 완료: {daily_price_count}건")
    print(f"signal_event 저장 완료: {signal_count}건")

    print("뉴스 수집 시작")
    signal_stock_codes = signal_df["stock_code"].dropna().astype(str).tolist()
    keyword_df = load_active_stock_keywords(signal_stock_codes)
    print(f"stock_keyword_map 활성 키워드 조회 완료: {len(keyword_df)}건")

    news_df = collect_news_for_signals(signal_df, keyword_df=keyword_df)
    if not news_df.empty:
        news_df = apply_news_relevance_scores(news_df)
    news_count = save_news_articles(news_df)
    print(f"news_article 저장 완료: {news_count}건")


def backfill_daily_price_command(
    start_date: date | None = None,
    end_date: date | None = None,
    limit_stocks: int | None = None,
) -> None:
    import time

    from collector.stock_collector import get_daily_stock_price_history
    from database.stock_repository import (
        get_min_pdf_signal_report_date,
        load_active_stock_master,
        save_daily_prices,
    )

    resolved_start = start_date or get_min_pdf_signal_report_date()
    if resolved_start is None:
        print("pdf_signal_item.report_date 데이터가 없어 백필 시작일을 결정할 수 없습니다.")
        return
    resolved_end = end_date or date.today()
    if resolved_start > resolved_end:
        raise ValueError("백필 시작일이 종료일보다 늦습니다.")

    master = load_active_stock_master(limit=limit_stocks)
    total_count = len(master)
    success_count = 0
    fail_count = 0
    saved_count = 0
    empty_count = 0
    errors: list[str] = []

    print(
        "daily_price 백필 시작: "
        f"{resolved_start.isoformat()} ~ {resolved_end.isoformat()}"
    )
    print(f"백필 대상 종목 수: {total_count}건")

    for index, row in enumerate(master.to_dict("records"), start=1):
        stock_code = str(row["stock_code"]).zfill(6)
        stock_name = str(row["stock_name"])
        market = str(row["market"])
        try:
            price_df = get_daily_stock_price_history(
                stock_code=stock_code,
                stock_name=stock_name,
                start_date=resolved_start,
                end_date=resolved_end,
                market=market,
            )
            if price_df.empty:
                empty_count += 1
            else:
                saved_count += save_daily_prices(price_df)
                success_count += 1
        except Exception as error:
            fail_count += 1
            message = f"{stock_code} {stock_name}: {error}"
            errors.append(message)
            print(f"[WARN] 백필 실패: {message}")

        if index % 100 == 0 or index == total_count:
            print(
                f"백필 진행: {index}/{total_count} "
                f"(성공 {success_count}건, 빈 데이터 {empty_count}건, "
                f"실패 {fail_count}건, 저장 {saved_count}행)"
            )

        time.sleep(0.05)

    print("daily_price 백필 완료")
    print(f"기간: {resolved_start.isoformat()} ~ {resolved_end.isoformat()}")
    print(f"대상 종목: {total_count}건")
    print(f"성공 종목: {success_count}건")
    print(f"빈 데이터 종목: {empty_count}건")
    print(f"실패 종목: {fail_count}건")
    print(f"daily_price upsert 행 수: {saved_count}행")
    if errors:
        print("실패 예시:")
        for message in errors[:10]:
            print(f"- {message}")


def _format_pct(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}%"


def _print_backtest_cases(title: str, rows: list[dict]) -> None:
    if not rows:
        return
    print(title)
    for row in rows[:10]:
        ret_d20 = row.get("ret_d20")
        ret_text = "-" if ret_d20 is None else f"{float(ret_d20):+.2f}%"
        print(
            f"- {row['stock_name']} {row['signal_date']} "
            f"entry {row['entry_date']} D+20 {ret_text}"
        )


def _print_500b_two_bearish_backtest_result(result: dict) -> None:
    params = result["params"]
    summary = result["summary"]
    source_stats = result.get("source_stats") or {}

    print("[500억봉 2음봉 백테스트]")
    print(f"기간: {params['from_date']} ~ {params['to_date']}")
    print(f"lookahead_days: {params['lookahead_days']}")
    print(f"volume_ratio: {float(params['volume_ratio']):.2f}")
    print(f"source: {params.get('source', 'both')}")
    print(f"signal_event 이벤트: {source_stats.get('signal_event_count', 0)}건")
    print(f"pdf_signal_item 이벤트: {source_stats.get('pdf_signal_item_count', 0)}건")
    print(f"매핑 성공: {source_stats.get('pdf_mapping_success_count', 0)}건")
    print(f"가격데이터 존재: {source_stats.get('price_data_event_count', 0)}건")
    if source_stats.get("event_count_after_source_dedupe") is not None:
        print(f"소스 중복 제거 후: {source_stats.get('event_count_after_source_dedupe', 0)}건")
    print(f"이벤트 수: {result['event_count']}건")
    print(f"결과 저장: {result['saved_count']}건")
    if _parse_date(params["to_date"]) > date.today():
        print("주의: to-date가 현재 날짜보다 미래입니다. 일부 수익률이 NULL일 수 있습니다.")
    if result.get("d20_null_count"):
        print(
            "주의: 최근 20거래일 이내 이벤트 또는 가격 데이터 부족 이벤트는 "
            "D+20 수익률이 NULL일 수 있습니다. "
            f"(NULL {result['d20_null_count']}건)"
        )
    if result.get("csv_path"):
        print(f"CSV: {result['csv_path']}")
    print()
    print("전략별 요약")
    print("-" * 98)
    print(
        f"{'전략명':<28} {'건수':>6} {'D+5승률':>9} {'D+5평균':>9} "
        f"{'D+10승률':>10} {'D+10평균':>10} {'20D Max':>9} {'20D Min':>9} {'손익비':>8}"
    )
    strategy_order = [
        "D0 종가매수",
        "첫 거래량감소 음봉",
        "거래량감소 연속 2음봉",
        "연속 2음봉 + 거래량 추가감소",
    ]
    for strategy_name in strategy_order:
        row = summary.get(strategy_name, {"count": 0})
        profit_loss_ratio = row.get("profit_loss_ratio")
        profit_loss_ratio_text = (
            "-"
            if profit_loss_ratio is None
            else f"{float(profit_loss_ratio):.2f}"
        )
        print(
            f"{strategy_name:<28} "
            f"{int(row.get('count') or 0):>6} "
            f"{_format_pct(row.get('d5_win_rate')):>9} "
            f"{_format_pct(row.get('d5_avg_return')):>9} "
            f"{_format_pct(row.get('d10_win_rate')):>10} "
            f"{_format_pct(row.get('d10_avg_return')):>10} "
            f"{_format_pct(row.get('avg_max_ret_20d')):>9} "
            f"{_format_pct(row.get('avg_min_ret_20d')):>9} "
            f"{profit_loss_ratio_text:>8}"
        )

    for strategy_name in strategy_order:
        row = summary.get(strategy_name)
        if not row:
            continue
        print()
        print(f"[{strategy_name}]")
        _print_backtest_cases("최고 사례 TOP 10", row.get("best_cases") or [])
        _print_backtest_cases("최악 사례 TOP 10", row.get("worst_cases") or [])


def backtest_500b_two_bearish_command(
    from_date: date,
    to_date: date,
    lookahead_days: int,
    volume_ratio: float,
    holding_days: list[int],
    min_d0_trade_amount: int,
    dedupe_window_days: int | None,
    export_csv: bool,
    source: str = "both",
    sweep_volume_ratio: list[float] | None = None,
) -> None:
    from database.backtest_repository import run_500b_two_bearish_backtest

    ratios = sweep_volume_ratio or [volume_ratio]
    sweep_rows = []
    for ratio in ratios:
        result = run_500b_two_bearish_backtest(
            from_date=from_date,
            to_date=to_date,
            lookahead_days=lookahead_days,
            volume_ratio=ratio,
            holding_days=holding_days,
            min_d0_trade_amount=min_d0_trade_amount,
            dedupe_window_days=dedupe_window_days,
            export_csv=export_csv,
            source=source,
        )
        _print_500b_two_bearish_backtest_result(result)
        two_bearish = result["summary"].get("거래량감소 연속 2음봉", {})
        sweep_rows.append(
            {
                "volume_ratio": ratio,
                "count": two_bearish.get("count", 0),
                "d5_win_rate": two_bearish.get("d5_win_rate"),
                "d5_avg_return": two_bearish.get("d5_avg_return"),
                "d10_win_rate": two_bearish.get("d10_win_rate"),
                "d10_avg_return": two_bearish.get("d10_avg_return"),
            }
        )

    if len(sweep_rows) > 1:
        print()
        print("[volume_ratio sweep 비교: 거래량감소 연속 2음봉]")
        print("-" * 72)
        print(
            f"{'ratio':>8} {'건수':>6} {'D+5승률':>10} {'D+5평균':>10} "
            f"{'D+10승률':>10} {'D+10평균':>10}"
        )
        for row in sweep_rows:
            print(
                f"{row['volume_ratio']:>8.2f} "
                f"{int(row['count'] or 0):>6} "
                f"{_format_pct(row.get('d5_win_rate')):>10} "
                f"{_format_pct(row.get('d5_avg_return')):>10} "
                f"{_format_pct(row.get('d10_win_rate')):>10} "
                f"{_format_pct(row.get('d10_avg_return')):>10}"
            )


def build_news_query(stock_name: str, search_term: str, term_type: str) -> str:
    if term_type == "STOCK_NAME":
        return search_term
    return f"{stock_name} {search_term}".strip()


def collect_news(
    stock_code: str | None = None,
    stock_name: str | None = None,
    max_terms: int = 10,
    max_news_per_term: int = 20,
) -> None:
    import pandas as pd

    from collector.news_collector import OUTPUT_COLUMNS, search_news_by_keyword
    from database.news_repository import (
        apply_news_relevance_scores,
        load_stock_for_news,
        load_stock_search_terms,
        save_news_articles,
    )

    stock = load_stock_for_news(stock_code=stock_code, stock_name=stock_name)
    if stock is None:
        target = stock_code or stock_name or "-"
        print(f"대상 종목을 찾을 수 없습니다: {target}")
        return

    term_df = load_stock_search_terms(stock["stock_name"], limit=max_terms)
    if term_df.empty:
        term_df = pd.DataFrame(
            [
                {
                    "search_term": stock["stock_name"],
                    "term_type": "STOCK_NAME",
                    "score": 100,
                }
            ]
        )

    frames: list[pd.DataFrame] = []
    collected_counts: dict[str, int] = {}
    search_query_map: dict[str, str] = {}
    error_terms: list[str] = []

    for row in term_df.itertuples(index=False):
        search_term = str(row.search_term).strip()
        term_type = str(row.term_type).strip()
        term_score = row.score
        if not search_term:
            continue
        search_query = build_news_query(stock["stock_name"], search_term, term_type)
        search_query_map[search_term] = search_query

        try:
            frame = search_news_by_keyword(
                keyword=search_query,
                stock_code=stock["stock_code"],
                stock_name=stock["stock_name"],
                display=max_news_per_term,
            )
        except RuntimeError as error:
            print(f"[WARN] 뉴스 검색 실패: {search_term} -> {search_query} - {error}")
            error_terms.append(f"{search_term} -> {search_query}")
            continue

        collected_counts[search_query] = len(frame)
        if frame.empty:
            continue

        frame = frame.copy()
        frame["search_term"] = search_term
        frame["search_query"] = search_query
        frame["search_term_type"] = term_type
        frame["search_term_score"] = term_score
        frames.append(frame)

    if frames:
        news_df = pd.concat(frames, ignore_index=True)
    else:
        news_df = pd.DataFrame(columns=OUTPUT_COLUMNS)

    raw_count = len(news_df)
    if not news_df.empty and "link" in news_df.columns:
        news_df = news_df.drop_duplicates(subset=["link"])

    news_df = apply_news_relevance_scores(news_df)
    saved_count = save_news_articles(news_df)
    duplicate_count = raw_count - saved_count
    relevant_count = int(news_df["is_relevant"].sum()) if not news_df.empty else 0
    irrelevant_count = len(news_df) - relevant_count
    average_score = (
        float(news_df["relevance_score"].mean()) if not news_df.empty else 0.0
    )

    print(f"대상 종목: {stock['stock_name']}")
    print(f"사용 검색어 수: {len(term_df)}")
    print("사용 검색어:")
    for row in term_df.itertuples(index=False):
        search_term = str(row.search_term).strip()
        term_type = str(row.term_type).strip()
        search_query = search_query_map.get(
            search_term,
            build_news_query(stock["stock_name"], search_term, term_type),
        )
        print(f"- {search_term} [{term_type}] -> {search_query}")
    print("검색 쿼리별 수집 건수:")
    for search_query, count in collected_counts.items():
        print(f"- {search_query}: {count}건")
    print(f"신규 저장 건수: {saved_count}건")
    print(f"중복 제외 건수: {duplicate_count}건")
    print(f"관련 뉴스 건수: {relevant_count}건")
    print(f"비관련 뉴스 건수: {irrelevant_count}건")
    print(f"평균 relevance_score: {average_score:.2f}")
    if error_terms:
        print("오류 검색어 목록: " + ", ".join(error_terms))
    else:
        print("오류 검색어 목록: 없음")


def ingest_pdf(pdf_dir: str, limit: int | None = None) -> None:
    from collector.pdf_ingestor import (
        detect_format_type,
        extract_pdf_text,
        find_pdf_files,
        parse_signal_evening_text,
    )
    from database.pdf_repository import save_pdf_signal_items

    pdf_files = find_pdf_files(pdf_dir, limit=limit)
    if not pdf_files:
        print(f"PDF 파일을 찾을 수 없습니다: {pdf_dir}")
        return

    summary_rows = []
    for pdf_file in pdf_files:
        row = {
            "pdf_file_name": pdf_file.name,
            "format_type": "unknown",
            "parsed_count": 0,
            "saved_count": 0,
            "status": "zero_parsed",
            "error_message": "",
        }

        try:
            text = extract_pdf_text(pdf_file)
            format_type = detect_format_type(text)
            signal_df = parse_signal_evening_text(
                text,
                pdf_file.name,
                format_type=format_type,
            )
            parsed_count = len(signal_df)
            row["format_type"] = format_type
            row["parsed_count"] = parsed_count

            saved_count = save_pdf_signal_items(signal_df)
            row["saved_count"] = saved_count
            row["status"] = "success" if parsed_count > 0 else "zero_parsed"
        except Exception as error:
            row["status"] = "error"
            row["error_message"] = str(error)

        summary_rows.append(row)

    _write_pdf_ingest_summary(summary_rows)
    _print_pdf_ingest_summary(summary_rows)


def _write_pdf_ingest_summary(summary_rows: list[dict]) -> None:
    output_dir = Path("data/pdf_inspect")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "ingest_summary.csv"
    fieldnames = [
        "pdf_file_name",
        "format_type",
        "parsed_count",
        "saved_count",
        "status",
        "error_message",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    zero_parse_files = [
        row["pdf_file_name"]
        for row in summary_rows
        if row["status"] == "zero_parsed"
    ]
    (output_dir / "zero_parse_files.txt").write_text(
        "\n".join(zero_parse_files),
        encoding="utf-8",
    )

    error_files = [
        row["pdf_file_name"]
        for row in summary_rows
        if row["status"] == "error"
    ]
    (output_dir / "error_files.txt").write_text(
        "\n".join(error_files),
        encoding="utf-8",
    )


def _print_pdf_ingest_summary(summary_rows: list[dict]) -> None:
    status_counts = {"success": 0, "zero_parsed": 0, "error": 0}
    for row in summary_rows:
        status_counts[row["status"]] += 1

    parsed_rows = sum(int(row["parsed_count"]) for row in summary_rows)
    saved_rows = sum(int(row["saved_count"]) for row in summary_rows)

    print(f"총 PDF: {len(summary_rows)}")
    print(f"success: {status_counts['success']}")
    print(f"zero_parsed: {status_counts['zero_parsed']}")
    print(f"error: {status_counts['error']}")
    print(f"parsed rows: {parsed_rows}")
    print(f"saved rows: {saved_rows}")


def inspect_pdf_format_command(pdf_dir: str, inspect_pages: int) -> None:
    from collector.pdf_ingestor import FORMAT_TYPES, inspect_pdf_formats

    files_by_format = inspect_pdf_formats(
        pdf_dir=pdf_dir,
        inspect_pages=inspect_pages,
    )

    total_count = sum(len(files) for files in files_by_format.values())
    print(f"PDF 포맷 검사 완료: {total_count}개")
    for format_type in FORMAT_TYPES:
        files = files_by_format[format_type]
        sample_names = ", ".join(path.name for path in files[:3]) or "-"
        print(f"{format_type}: {len(files)}개 / sample: {sample_names}")

    print("unknown 파일 목록 저장: data/pdf_inspect/unknown_files.txt")


def build_theme_map() -> None:
    from database.theme_repository import build_stock_theme_map

    result = build_stock_theme_map()
    print(f"theme_master 구축 완료: {result['theme_count']}건")
    print(f"stock_theme_map upsert 완료: {result['stock_theme_map_count']}건")


def seed_theme_alias() -> None:
    from database.theme_repository import seed_theme_aliases

    result = seed_theme_aliases()
    print(f"canonical theme seed 완료: {result['canonical_theme_count']}건")
    print(f"theme_alias seed 완료: {result['alias_count']}건")
    print(
        "미등록 canonical theme: "
        f"{result['missing_canonical_theme_count']}건"
    )


def seed_canonical_theme() -> None:
    from database.theme_repository import seed_canonical_themes

    result = seed_canonical_themes()
    print(f"canonical_theme_master seed 완료: {result['canonical_theme_count']}건")


def build_canonical_theme_map() -> None:
    from database.theme_repository import build_stock_canonical_theme_map

    result = build_stock_canonical_theme_map()
    print(
        "stock_canonical_theme_map upsert 완료: "
        f"{result['stock_canonical_theme_map_count']}건"
    )


def build_stock_profile() -> None:
    from database.theme_repository import build_stock_profiles

    result = build_stock_profiles()
    print(f"stock_profile upsert 완료: {result['stock_profile_count']}건")


def build_stock_knowledge() -> None:
    from database.theme_repository import build_stock_knowledge_graph

    result = build_stock_knowledge_graph()
    print(f"THEME node upsert 완료: {result['theme_node_count']}건")
    print(f"KEYWORD node upsert 완료: {result['keyword_node_count']}건")
    print(
        "stock_knowledge_graph upsert 완료: "
        f"{result['stock_knowledge_graph_count']}건"
    )


def seed_stock_keywords() -> None:
    from database.theme_repository import seed_stock_keywords as seed_keywords

    result = seed_keywords()
    print(f"stock_keyword_map seed 완료: {result['seeded_count']}건")
    print(f"seed 대상 종목 수: {result['stock_count']}건")
    if result["missing_stocks"]:
        print("stock_master 미등록 종목: " + ", ".join(result["missing_stocks"]))


def sync_stock_master_command() -> None:
    from collector.stock_collector import fetch_krx_stock_universe
    from database.stock_repository import upsert_stock_master_bulk

    print("KRX 전체 종목 universe 수집 시작")
    try:
        universe = fetch_krx_stock_universe()
    except Exception as error:
        print(f"KRX universe 수집 실패: {error}")
        print("stock_master를 변경하지 않았습니다.")
        return

    saved_count = upsert_stock_master_bulk(universe)
    market_counts = universe.groupby("market")["stock_code"].count().to_dict()

    print(f"최종 수집 종목 수: {len(universe)}건")
    for market in ("KOSPI", "KOSDAQ"):
        print(f"{market}: {market_counts.get(market, 0)}건")
    print(f"stock_master upsert 완료: {saved_count}건")


def build_search_terms() -> None:
    from database.theme_repository import run_build_search_terms

    result = run_build_search_terms()
    print(f"생성/업데이트 총 건수: {result['upserted_count']}건")
    print(f"대상 종목 수: {result['stock_count']}건")
    print(f"검색어 총 건수: {result['search_term_count']}건")
    print("상위 예시 5개 종목의 검색어 목록:")
    for example in result["examples"]:
        print(f"- {example['stock_name']}: {example['search_terms']}")


def score_news_relevance_command(stock_name: str, limit: int | None = None) -> None:
    from database.news_repository import score_news_relevance

    result = score_news_relevance(stock_name=stock_name, limit=limit)
    print(f"relevance_score 갱신 완료: {result['updated_count']}건")
    print(f"관련 뉴스 건수: {result['relevant_count']}건")
    print(f"비관련 뉴스 건수: {result['irrelevant_count']}건")
    print(f"평균 relevance_score: {result['average_relevance_score']:.2f}")


def analyze_stock_command(
    stock_name: str,
    report_date: date,
    limit: int,
    mock: bool,
) -> None:
    from database.news_repository import StockAnalysisLlmError, analyze_stock_news

    try:
        result = analyze_stock_news(
            stock_name=stock_name,
            report_date=report_date,
            limit=limit,
            mock=mock,
        )
    except StockAnalysisLlmError as error:
        print(f"AI 분석 실패: {error}")
        if error.raw_response:
            preview = error.raw_response[:500]
            suffix = "..." if len(error.raw_response) > 500 else ""
            print(f"LLM 원문 응답 일부: {preview}{suffix}")
        print("분석 결과를 저장하지 않았습니다.")
        return

    summary = result.get("summary") or ""
    preview = summary[:120] + ("..." if len(summary) > 120 else "")

    print(f"대상 종목: {result['stock_name']}")
    print(f"분석 기준일: {result['report_date']}")
    print(f"사용 뉴스 수: {result['source_news_count']}건")
    print(f"sentiment: {result['sentiment']}")
    print(f"confidence_score: {result['confidence_score']:.2f}")
    print(f"summary: {preview}")


def test_investment_grade_command(stock_name: str) -> None:
    import json

    from database.news_repository import (
        get_relevant_news_for_analysis,
        get_stock_analysis,
        get_stock_knowledge_context,
    )
    from database.pattern_repository import get_stock_pattern_stats
    from report.investment_grade_engine import calculate_investment_grade

    news_items = get_relevant_news_for_analysis(stock_name=stock_name, limit=20)
    news_text = "\n".join(
        " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("description") or ""),
            ]
        )
        for item in news_items
    )
    analysis_df = get_stock_analysis(stock_name=stock_name)
    ai_analysis_text = ""
    if not analysis_df.empty:
        row = analysis_df.iloc[0].to_dict()
        ai_analysis_text = "\n".join(
            str(row.get(column) or "")
            for column in (
                "summary",
                "key_issues",
                "positive_points",
                "risk_points",
                "theme_points",
                "tomorrow_checkpoints",
                "knowledge_points",
                "pattern_points",
            )
        )

    result = calculate_investment_grade(
        stock_name=stock_name,
        news_text=news_text,
        ai_analysis_text=ai_analysis_text,
        knowledge_context=get_stock_knowledge_context(stock_name),
        pattern_stats=get_stock_pattern_stats(stock_name),
    )
    breakdown = result.get("score_breakdown") or {}
    debug = result.get("debug") or {}
    print(f"investment_score: {result.get('investment_score')}")
    print(f"investment_grade: {result.get('investment_grade')}")
    print(
        "score_breakdown: "
        f"pattern={breakdown.get('pattern', 0)}, "
        f"knowledge={breakdown.get('knowledge', 0)}, "
        f"news={breakdown.get('news', 0)}"
    )
    print(f"pattern_boost_applied: {debug.get('pattern_boost_applied', False)}")
    print(f"risk_cap_applied: {debug.get('risk_cap_applied', False)}")
    if debug.get("risk_cap_reason"):
        print(f"risk_cap_reason: {debug['risk_cap_reason']}")
    print()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def backfill_investment_grade_command(report_date: date) -> None:
    from database.news_repository import backfill_investment_grades

    result = backfill_investment_grades(report_date)
    print(f"투자등급 백필 기준일: {result['report_date']}")
    print(f"대상: {result['target_count']}건")
    print(f"업데이트: {result['updated_count']}건")
    print(f"실패: {result['error_count']}건")
    if result["errors"]:
        print("실패 목록:")
        for row in result["errors"][:20]:
            print(f"- {row['stock_name']}: {row['error']}")


def check_missing_analysis_command(report_date: date, run_missing: bool = False) -> None:
    from database.db import get_connection

    sql = """
        SELECT DISTINCT
            sm.stock_name
        FROM signal_event se
        JOIN stock_master sm
            ON sm.stock_code = se.stock_code
        LEFT JOIN LATERAL (
            SELECT id
            FROM stock_analysis sa
            WHERE sa.stock_name = sm.stock_name
                AND sa.analysis_date::date = %(report_date)s
            ORDER BY sa.analysis_date DESC, sa.id DESC
            LIMIT 1
        ) latest_analysis ON TRUE
        WHERE se.signal_date = %(report_date)s
            AND latest_analysis.id IS NULL
        ORDER BY sm.stock_name
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"report_date": report_date})
            missing_stocks = [row[0] for row in cursor.fetchall()]

    print("분석 누락 종목:")
    if missing_stocks:
        for stock_name in missing_stocks:
            print(f"* {stock_name}")
    print(f"총 {len(missing_stocks)}개")

    if not run_missing or not missing_stocks:
        return

    from database.news_repository import StockAnalysisLlmError, analyze_stock_news

    success_count = 0
    fail_rows: list[tuple[str, str]] = []
    for stock_name in missing_stocks:
        try:
            analyze_stock_news(
                stock_name=stock_name,
                report_date=report_date,
                limit=20,
                mock=False,
            )
            success_count += 1
            print(f"분석 완료: {stock_name}")
        except StockAnalysisLlmError as error:
            fail_rows.append((stock_name, str(error)))
            print(f"분석 실패: {stock_name} - {error}")
        except Exception as error:
            fail_rows.append((stock_name, str(error)))
            print(f"분석 실패: {stock_name} - {error}")

    print(f"자동 분석 성공: {success_count}개")
    print(f"자동 분석 실패: {len(fail_rows)}개")


def analyze_signals_command(report_date: date, limit: int, mock: bool) -> None:
    from database.news_repository import analyze_signal_stocks

    result = analyze_signal_stocks(report_date=report_date, limit=limit, mock=mock)

    print(f"분석 기준일: {result['report_date']}")
    print(f"대상 종목 수: {result['target_count']}건")
    print(f"분석 성공: {result['success_count']}건")
    print(f"분석 실패: {result['error_count']}건")

    if result["results"]:
        print("분석 결과:")
        for row in result["results"]:
            summary = row.get("summary") or ""
            preview = summary[:80] + ("..." if len(summary) > 80 else "")
            print(
                f"- {row['stock_name']}: "
                f"{row['sentiment']} / "
                f"{row['confidence_score']:.2f} / "
                f"뉴스 {row['source_news_count']}건 / "
                f"{preview}"
            )

    if result["errors"]:
        print("오류 목록:")
        for row in result["errors"]:
            print(f"- {row['stock_name']}: {row['error']}")


def analyze_signal_stocks_command(
    report_date: date,
    limit_news: int,
    mock: bool,
) -> None:
    from database.news_repository import analyze_signal_event_stocks

    result = analyze_signal_event_stocks(
        report_date=report_date,
        limit_news=limit_news,
        mock=mock,
    )

    print(f"분석 기준일: {result['report_date']}")
    print(f"분석 대상 종목 수: {result['target_count']}건")
    print(f"성공: {result['success_count']}건")
    print(f"스킵: {result['skip_count']}건")
    print(f"실패: {result['error_count']}건")

    if result["skipped"]:
        print("스킵 종목 목록:")
        for row in result["skipped"]:
            print(f"- {row['stock_name']}: {row['reason']}")

    if result["errors"]:
        print("실패 종목 목록:")
        for row in result["errors"]:
            print(f"- {row['stock_name']}: {row['error']}")


def analyze_daily_themes_command(
    report_date: date,
    limit_news_per_stock: int,
    mock: bool,
) -> None:
    from database.news_repository import StockAnalysisLlmError, analyze_daily_themes

    try:
        result = analyze_daily_themes(
            report_date=report_date,
            limit_news_per_stock=limit_news_per_stock,
            mock=mock,
        )
    except StockAnalysisLlmError as error:
        print(f"일간 테마 분석 실패: {error}")
        if error.raw_response:
            preview = error.raw_response[:500]
            suffix = "..." if len(error.raw_response) > 500 else ""
            print(f"LLM 원문 응답 일부: {preview}{suffix}")
        print("분석 결과를 저장하지 않았습니다.")
        return

    summary = result.get("market_summary") or ""
    preview = summary[:160] + ("..." if len(summary) > 160 else "")

    print(f"분석일: {result['report_date']}")
    print(f"500억봉 종목 수: {result['source_stock_count']}건")
    if result["source_stock_count"] == 0:
        print(
            "해당 날짜의 signal_event 데이터가 없습니다. "
            f"python main.py run --date {result['report_date']} 실행 여부를 확인하세요."
        )
    print(f"관련 뉴스 수: {result['source_news_count']}건")
    print(f"confidence_score: {result['confidence_score']:.2f}")
    print(f"market_summary: {preview}")


def summarize_news_command(
    report_date: date,
    stock_name: str | None,
    limit: int,
    mock: bool,
) -> None:
    from database.news_repository import summarize_news_articles

    result = summarize_news_articles(
        report_date=report_date,
        stock_name=stock_name,
        limit=limit,
        mock=mock,
    )
    print(f"뉴스 요약 기준일: {result['report_date']}")
    print(f"요약 대상 뉴스 수: {result['target_count']}건")
    print(f"성공: {result['success_count']}건")
    print(f"실패: {result['error_count']}건")
    if result["errors"]:
        print("실패 뉴스 목록:")
        for row in result["errors"]:
            print(f"- {row['id']} {row['title']}: {row['error']}")


def generate_report_command(report_date: date) -> None:
    from report.report_generator import generate_daily_report

    output_path = generate_daily_report(report_date)
    print("PDF 생성 완료:")
    print(output_path)


def build_pattern_stats_command() -> None:
    from database.pattern_repository import build_stock_pattern_stats

    result = build_stock_pattern_stats()
    print(f"stock_pattern_stats 구축 완료: {result['stock_count']}개 종목")
    print(f"pdf_signal_item 종목명 매핑 실패: {result['pdf_unmatched_count']}건")


def _print_pipeline_failure(step_label: str, error: Exception) -> None:
    import traceback

    print(f"{step_label} 실패: {error}")
    traceback.print_exc()


def run_daily_report_command(
    report_date: date,
    mock: bool = False,
    limit_stocks: int | None = None,
) -> None:
    from database.pattern_repository import build_stock_pattern_stats
    from database.news_repository import (
        analyze_daily_themes,
        analyze_signal_event_stocks,
        summarize_news_articles,
    )
    from report.report_generator import generate_daily_report

    current_step = "준비"
    try:
        current_step = "[1/6] 주가 수집 및 500억봉 탐지"
        print("[1/6] 주가 수집 및 500억봉 탐지 시작")
        run(report_date, limit_stocks=limit_stocks)
        print("[1/6] 완료")

        current_step = "[2/6] 뉴스 요약"
        print("[2/6] 뉴스 요약 시작")
        news_summary_result = summarize_news_articles(
            report_date=report_date,
            limit=100,
            mock=mock,
        )
        print(
            "[2/6] 완료 "
            f"(대상 {news_summary_result['target_count']}건, "
            f"성공 {news_summary_result['success_count']}건, "
            f"실패 {news_summary_result['error_count']}건)"
        )

        current_step = "[3/6] 패턴 통계 갱신"
        print("[3/6] 패턴 통계 갱신 시작")
        pattern_result = build_stock_pattern_stats()
        print(
            "[3/6] 완료 "
            f"(종목 {pattern_result['stock_count']}건, "
            f"PDF 매핑 실패 {pattern_result['pdf_unmatched_count']}건)"
        )

        current_step = "[4/6] 500억봉 종목 AI 분석"
        print("[4/6] 500억봉 종목 AI 분석 시작")
        signal_result = analyze_signal_event_stocks(
            report_date=report_date,
            limit_news=20,
            mock=mock,
        )
        print(
            "[4/6] 완료 "
            f"(대상 {signal_result['target_count']}건, "
            f"성공 {signal_result['success_count']}건, "
            f"스킵 {signal_result['skip_count']}건, "
            f"실패 {signal_result['error_count']}건)"
        )

        current_step = "[5/6] 일일 테마 분석"
        print("[5/6] 일일 테마 분석 시작")
        theme_result = analyze_daily_themes(
            report_date=report_date,
            limit_news_per_stock=5,
            mock=mock,
        )
        print(
            "[5/6] 완료 "
            f"(500억봉 {theme_result['source_stock_count']}건, "
            f"뉴스 {theme_result['source_news_count']}건)"
        )

        current_step = "[6/6] PDF 생성"
        print("[6/6] PDF 생성 시작")
        output_path = generate_daily_report(report_date)
        print(f"[6/6] 완료: {output_path}")
    except Exception as error:
        _print_pipeline_failure(current_step, error)
        raise SystemExit(1) from error

    print("일일 리포트 생성 완료:")
    print(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock research system")
    parser.add_argument("command", nargs="?", help="Command to run")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD format")
    parser.add_argument("--from-date", help="Backtest start date in YYYY-MM-DD format")
    parser.add_argument("--to-date", help="Backtest end date in YYYY-MM-DD format")
    parser.add_argument("--stock-code", help="Stock code for collect-news command")
    parser.add_argument("--stock-name", help="Stock name for collect-news command")
    parser.add_argument(
        "--max-terms",
        type=int,
        default=10,
        help="Maximum number of search terms for collect-news command",
    )
    parser.add_argument(
        "--max-news-per-term",
        type=int,
        default=20,
        help="Maximum number of news articles per search term",
    )
    parser.add_argument(
        "--pdf-dir",
        default="data/pdfs",
        help="PDF directory for ingest-pdf command",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of rows/PDFs to process",
    )
    parser.add_argument(
        "--inspect-pages",
        type=int,
        default=5,
        help="Number of PDF pages to inspect for format detection",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock output for analyze-stock without calling an LLM",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run automatic remediation for commands that support it",
    )
    parser.add_argument(
        "--limit-news-per-stock",
        type=int,
        default=5,
        help="Maximum relevant news rows per stock for analyze-daily-themes",
    )
    parser.add_argument(
        "--limit-stocks",
        type=int,
        help="Maximum stock count for run command",
    )
    parser.add_argument(
        "--limit-news",
        type=int,
        default=20,
        help="Maximum relevant news rows per stock for analyze-signal-stocks",
    )
    parser.add_argument(
        "--lookahead-days",
        type=int,
        default=20,
        help="Lookahead trading days for two-bearish backtest",
    )
    parser.add_argument(
        "--volume-ratio",
        type=float,
        default=0.3,
        help="Volume threshold ratio to D0 volume for two-bearish backtest",
    )
    parser.add_argument(
        "--sweep-volume-ratio",
        help="Comma separated volume ratios, e.g. 0.1,0.2,0.3,0.4",
    )
    parser.add_argument(
        "--holding-days",
        default="3,5,10,20",
        help="Comma separated holding days for backtest returns",
    )
    parser.add_argument(
        "--min-d0-trade-amount",
        type=int,
        default=50_000_000_000,
        help="Minimum D0 trading value for signal events",
    )
    parser.add_argument(
        "--dedupe-window-days",
        type=int,
        help="Remove same-stock signal events within this many trading days",
    )
    parser.add_argument(
        "--source",
        choices=["signal_event", "pdf_signal_item", "both"],
        default="both",
        help="Backtest event source: signal_event, pdf_signal_item, or both",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export backtest result rows to CSV",
    )
    args = parser.parse_args()

    if args.command == "test-db":
        if test_connection():
            print("DB 연결 성공")
        return

    if args.command == "run":
        run(_parse_date(args.date), limit_stocks=args.limit_stocks)
        return

    if args.command == "backfill-daily-price":
        backfill_daily_price_command(
            start_date=_parse_date(args.start_date) if args.start_date else None,
            end_date=_parse_date(args.end_date) if args.end_date else None,
            limit_stocks=args.limit_stocks,
        )
        return

    if args.command == "backtest-500b-two-bearish":
        if not args.from_date or not args.to_date:
            parser.error("backtest-500b-two-bearish requires --from-date and --to-date")
        backtest_500b_two_bearish_command(
            from_date=_parse_date(args.from_date),
            to_date=_parse_date(args.to_date),
            lookahead_days=args.lookahead_days,
            volume_ratio=args.volume_ratio,
            holding_days=_parse_int_list(args.holding_days),
            min_d0_trade_amount=args.min_d0_trade_amount,
            dedupe_window_days=args.dedupe_window_days,
            export_csv=args.export_csv,
            source=args.source,
            sweep_volume_ratio=(
                _parse_float_list(args.sweep_volume_ratio)
                if args.sweep_volume_ratio
                else None
            ),
        )
        return

    if args.command == "run-daily-report":
        if not args.date:
            parser.error("run-daily-report requires --date")
        run_daily_report_command(
            report_date=_parse_date(args.date),
            mock=args.mock,
            limit_stocks=args.limit_stocks,
        )
        return

    if args.command == "sync-stock-master":
        sync_stock_master_command()
        return

    if args.command == "build-pattern-stats":
        build_pattern_stats_command()
        return

    if args.command == "collect-news":
        if not args.stock_code and not args.stock_name:
            parser.error("collect-news requires --stock-code or --stock-name")
        collect_news(
            stock_code=args.stock_code,
            stock_name=args.stock_name,
            max_terms=args.max_terms,
            max_news_per_term=args.max_news_per_term,
        )
        return

    if args.command == "ingest-pdf":
        ingest_pdf(args.pdf_dir, limit=args.limit)
        return

    if args.command == "inspect-pdf-formats":
        inspect_pdf_format_command(args.pdf_dir, inspect_pages=args.inspect_pages)
        return

    if args.command == "build-theme-map":
        build_theme_map()
        return

    if args.command == "seed-theme-alias":
        seed_theme_alias()
        return

    if args.command == "seed-canonical-theme":
        seed_canonical_theme()
        return

    if args.command == "build-canonical-theme-map":
        build_canonical_theme_map()
        return

    if args.command == "build-stock-profile":
        build_stock_profile()
        return

    if args.command == "build-stock-knowledge":
        build_stock_knowledge()
        return

    if args.command == "seed-stock-keywords":
        seed_stock_keywords()
        return

    if args.command == "build-search-terms":
        build_search_terms()
        return

    if args.command == "score-news-relevance":
        if not args.stock_name:
            parser.error("score-news-relevance requires --stock-name")
        score_news_relevance_command(args.stock_name, limit=args.limit)
        return

    if args.command == "analyze-stock":
        if not args.stock_name:
            parser.error("analyze-stock requires --stock-name")
        analyze_stock_command(
            stock_name=args.stock_name,
            report_date=_parse_date(args.date),
            limit=args.limit or 20,
            mock=args.mock,
        )
        return

    if args.command == "test-investment-grade":
        if not args.stock_name:
            parser.error("test-investment-grade requires --stock-name")
        test_investment_grade_command(args.stock_name)
        return

    if args.command == "backfill-investment-grade":
        if not args.date:
            parser.error("backfill-investment-grade requires --date")
        backfill_investment_grade_command(_parse_date(args.date))
        return

    if args.command == "check-missing-analysis":
        if not args.date:
            parser.error("check-missing-analysis requires --date")
        check_missing_analysis_command(
            report_date=_parse_date(args.date),
            run_missing=args.run,
        )
        return

    if args.command == "analyze-signals":
        analyze_signals_command(
            report_date=_parse_date(args.date),
            limit=args.limit or 20,
            mock=args.mock,
        )
        return

    if args.command == "analyze-signal-stocks":
        if not args.date:
            parser.error("analyze-signal-stocks requires --date")
        analyze_signal_stocks_command(
            report_date=_parse_date(args.date),
            limit_news=args.limit_news,
            mock=args.mock,
        )
        return

    if args.command == "summarize-news":
        if not args.date:
            parser.error("summarize-news requires --date")
        summarize_news_command(
            report_date=_parse_date(args.date),
            stock_name=args.stock_name,
            limit=args.limit or 100,
            mock=args.mock,
        )
        return

    if args.command == "analyze-daily-themes":
        if not args.date:
            parser.error("analyze-daily-themes requires --date")
        analyze_daily_themes_command(
            report_date=_parse_date(args.date),
            limit_news_per_stock=args.limit_news_per_stock,
            mock=args.mock,
        )
        return

    if args.command == "generate-report":
        if not args.date:
            parser.error("generate-report requires --date")
        generate_report_command(_parse_date(args.date))
        return

    print("Stock research system scaffold")


if __name__ == "__main__":
    main()
