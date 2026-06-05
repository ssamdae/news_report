import argparse
from datetime import date, datetime

from database.db import test_connection


def _parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def run(target_date: date) -> None:
    from collector.news_collector import collect_news_for_signals
    from collector.stock_collector import collect_daily_stocks
    from database.news_repository import save_news_articles
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
    news_df = collect_news_for_signals(signal_df)
    news_count = save_news_articles(news_df)
    print(f"news_article 저장 완료: {news_count}건")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock research system")
    parser.add_argument("command", nargs="?", help="Command to run")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format")
    args = parser.parse_args()

    if args.command == "test-db":
        if test_connection():
            print("DB 연결 성공")
        return

    if args.command == "run":
        run(_parse_date(args.date))
        return

    print("Stock research system scaffold")


if __name__ == "__main__":
    main()
