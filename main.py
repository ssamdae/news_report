import argparse
import csv
from datetime import date, datetime
from pathlib import Path

from database.db import test_connection


def _parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def run(target_date: date) -> None:
    from collector.news_collector import collect_news_for_signals
    from collector.stock_collector import collect_daily_stocks
    from database.news_repository import load_active_stock_keywords, save_news_articles
    from database.signal_event_repository import save_signal_events
    from database.stock_repository import save_daily_prices, save_stock_master
    from filter.signal_filter import filter_500eok_signal

    print(f"주가 수집 시작: {target_date.isoformat()}")
    stock_df = collect_daily_stocks(target_date)
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
    news_count = save_news_articles(news_df)
    print(f"news_article 저장 완료: {news_count}건")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock research system")
    parser.add_argument("command", nargs="?", help="Command to run")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format")
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
    args = parser.parse_args()

    if args.command == "test-db":
        if test_connection():
            print("DB 연결 성공")
        return

    if args.command == "run":
        run(_parse_date(args.date))
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

    if args.command == "analyze-signals":
        analyze_signals_command(
            report_date=_parse_date(args.date),
            limit=args.limit or 20,
            mock=args.mock,
        )
        return

    print("Stock research system scaffold")


if __name__ == "__main__":
    main()
