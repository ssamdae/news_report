# Stock Research System

Oracle Cloud Ubuntu 24.04, Python 3.12 기준 한국 주식 500억봉 후보를 수집하고 저장하는 프로젝트입니다.

## 실행 환경

- OS: Ubuntu 24.04 LTS
- Python: 3.12
- Database: PostgreSQL
- Data source: Naver Finance daily price page

## 초기 설정

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 네이버 검색 API 인증 정보를 설정하세요.

```bash
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
```

## 종목 마스터 준비

기본 수집기는 `data/stock_master.csv` 파일을 읽습니다.

CSV 형식:

```csv
stock_code,stock_name,market
005930,삼성전자,KOSPI
086520,에코프로,KOSDAQ
```

현재 저장소에는 실행 확인용 예시 `data/stock_master.csv`가 포함되어 있습니다. 실제 운영 전에는 KOSPI/KOSDAQ 전체 종목으로 교체하세요.

다른 경로의 CSV를 쓰려면 환경변수를 지정할 수 있습니다.

```bash
export STOCK_MASTER_CSV=/path/to/stock_master.csv
```

## 주가 수집 실행

```bash
python3.12 main.py run --date 2026-06-04
```

수집 흐름:

1. 종목 마스터 로드
2. 네이버 금융에서 종목별 일봉 수집
3. 전일 종가 계산
4. 500억봉 필터 적용
5. `stock_master`, `daily_price`, `signal_event` 저장
6. 500억봉 종목 기준 네이버 뉴스 검색 API 수집
7. `news_article` 저장

네이버 요청 차단을 줄이기 위해 종목별 요청 사이에 기본 0.2초 대기합니다. 환경변수를 지정해도 수집기는 0.1~0.3초 범위로 제한합니다.

```bash
export NAVER_REQUEST_SLEEP_SECONDS=0.3
```

## 수집 컬럼

수집기는 기존 필터와 DB 저장 로직을 유지하기 위해 다음 컬럼을 반환합니다.

- `trade_date`
- `market`
- `stock_code`
- `stock_name`
- `open_price`
- `high_price`
- `low_price`
- `close_price`
- `prev_close_price`
- `volume`
- `trading_value`

네이버 일봉 페이지는 거래대금을 직접 제공하지 않으므로 `trading_value`는 `close_price * volume`으로 산출합니다.

## DB 테스트

```bash
python3.12 main.py test-db
```
