# 2026년 8월 500억봉·당일 투자자 수급 시험

기존 `signal_event`나 DB를 사용하지 않는 별도 실험입니다. KOSPI/KOSDAQ 일별 전 종목 OHLCV를 조회하고, 조건에 맞는 종목에 대해서만 당일 투자자별 순매수금액을 조회합니다.

```bash
cd ~/apps/news_report
git pull origin main
source .venv/bin/activate
python scripts/basebar_scan_202608.py
```

결과: `output/basebar_202608_test.csv` (UTF-8 BOM, 엑셀에서 열기 가능). 가격 조건만 확인하려면 `--no-flow`를 붙입니다. 별도 파일 경로는 `--output`으로 지정할 수 있습니다. 실행 전후 `git status`에서 생성된 CSV를 커밋하지 않도록 주의하세요.

판정식은 거래대금 ≥ 50,000,000,000원, 고가 ≥ 전일 종가 × 1.15, 고가 ≥ 당일 저가 × 1.15, 종가 ≥ 시가 × 1.09입니다. 비교는 정수 비율로 계산하여 정확한 경계값을 포함합니다. 첫 8월 거래일의 `C(1)`을 구하기 위해 7월 마지막 거래일 자료도 수집합니다.

`*_net`은 원 단위 당일 순매수금액이고 `*_net_ratio`는 그 값 ÷ 기준봉 실제 거래대금 × 100(%)입니다. `investor_flow_status`는 `ok`, `missing`, `error`, `skipped` 중 하나입니다. 수급 미조회 시 값은 공란이며 0으로 가정하지 않습니다. `외국인`과 `기타외국인`은 원천 분류 그대로 별도로 표시합니다.

실행 결과의 종목 수, 8월 거래일 수, `investor_flow_status` 분포와 실제 키움 조건검색 후보를 대조하세요. pykrx/KRX 제공 데이터 장애가 있으면 스캔은 중단되고, 일부 수급 조회 실패는 해당 행에 표시됩니다. 서버의 pykrx 설치 버전과 KRX 응답에 따라 실제 조회 결과가 달라질 수 있습니다.
