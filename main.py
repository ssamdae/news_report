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


def collect_news(stock_code: str) -> None:
    import pandas as pd

    from collector.news_collector import collect_news_for_signals
    from database.news_repository import load_active_stock_keywords, save_news_articles
    from database.stock_repository import load_stock_master_by_code

    stock_code = stock_code.strip()
    if not stock_code:
        raise ValueError("--stock-code must not be empty")

    stock = load_stock_master_by_code(stock_code)
    if stock is None:
        print(f"stock_master에서 종목을 찾을 수 없습니다: {stock_code}")
        return

    print(f"뉴스 단독 수집 시작: {stock['stock_name']} ({stock['stock_code']})")
    keyword_df = load_active_stock_keywords([stock["stock_code"]])
    print(f"stock_keyword_map 활성 키워드 조회 완료: {len(keyword_df)}건")

    stock_df = pd.DataFrame(
        [
            {
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
            }
        ]
    )
    news_df = collect_news_for_signals(stock_df, keyword_df=keyword_df)
    news_count = save_news_articles(news_df)
    print(f"news_article 저장 완료: {news_count}건")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock research system")
    parser.add_argument("command", nargs="?", help="Command to run")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format")
    parser.add_argument("--stock-code", help="Stock code for collect-news command")
    parser.add_argument(
        "--pdf-dir",
        default="data/pdfs",
        help="PDF directory for ingest-pdf command",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of PDFs to ingest",
    )
    parser.add_argument(
        "--inspect-pages",
        type=int,
        default=5,
        help="Number of PDF pages to inspect for format detection",
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
        if not args.stock_code:
            parser.error("collect-news requires --stock-code")
        collect_news(args.stock_code)
        return

    if args.command == "ingest-pdf":
        ingest_pdf(args.pdf_dir, limit=args.limit)
        return

    if args.command == "inspect-pdf-formats":
        inspect_pdf_format_command(args.pdf_dir, inspect_pages=args.inspect_pages)
        return

    print("Stock research system scaffold")


if __name__ == "__main__":
    main()
