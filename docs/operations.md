# news_report 운영 메모

## 수동 실행

서버 기본 경로는 `/home/ubuntu/news_report`입니다.

```bash
cd /home/ubuntu/news_report
source venv/bin/activate
set -a; source .env; set +a

python3 main.py run-daily-report
python3 main.py run-daily-report --date 2026-06-09 --mock
python3 main.py generate-report --date 2026-06-09
```

## 스크립트 실행

운영 스크립트는 프로젝트 루트, `.env`, venv python, 로그 경로를 자동 처리합니다.

```bash
chmod +x scripts/run_daily_report.sh

scripts/run_daily_report.sh --date 2026-06-09 --mock --skip-news --skip-analysis --skip-report
scripts/run_daily_report.sh --date 2026-06-09 --mock --skip-news
scripts/run_daily_report.sh
```

로그 파일명은 실행일 기준입니다.

```text
logs/daily_report_YYYY-MM-DD.log
```

다른 경로에서 실행해야 하면 환경변수로 override할 수 있습니다.

```bash
NEWS_REPORT_PROJECT_DIR=/home/ubuntu/news_report \
NEWS_REPORT_PYTHON=/home/ubuntu/news_report/venv/bin/python3 \
/home/ubuntu/news_report/scripts/run_daily_report.sh
```

## cron 등록 후보

이번 단계에서는 실제 crontab을 수정하지 않습니다.

서버 timezone이 `Asia/Seoul`인 경우:

```cron
20 16 * * 1-5 /home/ubuntu/news_report/scripts/run_daily_report.sh
```

서버 timezone이 UTC인 경우:

```cron
20 7 * * 1-5 /home/ubuntu/news_report/scripts/run_daily_report.sh
```

서버 timezone 확인:

```bash
timedatectl
```

한국 휴장일은 cron만으로 제외되지 않습니다. 휴장일 자동 제외는 추후 영업일 캘린더 연동으로 보강합니다.

## 로그 확인

최근 로그:

```bash
ls -lh logs | tail
```

오늘 로그:

```bash
tail -120 logs/daily_report_$(date +%Y-%m-%d).log
```

에러 검색:

```bash
grep -i "error\|ERROR\|Traceback\|failed\|실패" logs/daily_report_$(date +%Y-%m-%d).log
```

스크립트는 시작 시각, 종료 시각, 실행 명령, exit code를 로그에 남깁니다.

## PDF 위치

PDF는 날짜별 폴더에 생성됩니다.

```text
reports/YYYY-MM-DD/daily_report_YYYY-MM-DD.pdf
```

최근 PDF 확인:

```bash
find reports -name "daily_report_*.pdf" -type f -printf "%TY-%Tm-%Td %TH:%TM %p\n" | sort | tail -10
```

## snapshot 관련 옵션

기본 실행은 기존 snapshot이 있으면 snapshot을 사용합니다.

```bash
python3 main.py generate-report --date 2026-06-09
```

같은 날짜 리포트 숫자를 현재 DB 기준으로 새로 계산하려면 `--refresh-snapshot`을 사용합니다.

```bash
scripts/run_daily_report.sh --date 2026-06-09 --refresh-snapshot
python3 main.py generate-report --date 2026-06-09 --refresh-snapshot
```

임시 검증 목적으로 현재 DB 기준 PDF만 생성하고 snapshot을 읽거나 저장하지 않으려면 `--no-snapshot`을 사용합니다.

```bash
python3 main.py generate-report --date 2026-06-09 --no-snapshot
```

운영 cron에서는 snapshot 옵션을 지정하지 않습니다.

## 재실행 정책

같은 날짜를 재실행하면 다음 정책을 따릅니다.

- `daily_price`: `stock_code`, `trade_date` 기준 upsert
- `signal_event`: `signal_date`, `stock_code`, `signal_name` 기준 upsert
- `news_article`: `link` 기준 중복 저장 방지
- `stock_analysis`: `stock_name`, `analysis_date::date` 기준 최신 row update
- PDF: 같은 파일 경로에 덮어쓰기
- report snapshot: 기본 실행은 기존 snapshot 사용, `--refresh-snapshot`에서만 덮어쓰기

## 주의사항

- 실제 cron 등록은 운영자가 crontab을 확인한 뒤 별도 진행합니다.
- 장 마감 직후 데이터 제공 지연이 있을 수 있으므로 최초 운영 시간은 16:20 KST를 기본 후보로 둡니다.
- 외부 API나 OpenAI 장애 시 로그의 `[DailyReport][ERROR]`와 `Traceback`을 확인합니다.
- 한국 휴장일 자동 제외는 아직 적용하지 않았습니다.
