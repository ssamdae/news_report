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

## 눌림 → 기준봉 종가 재돌파 → 안착 실험

기준봉 CSV를 확인한 뒤 다음 스크립트로 이후 가격 경로를 별도 산출합니다. 기본 가격 조회원은 네이버 차트 XML 일봉(`fchart.stock.naver.com/sise.nhn`)이며, KRX 로그인이 필요하지 않습니다. 기준봉 날짜 또는 네이버 응답이 누락되면 완료된 CSV를 쓰지 않고 중단합니다. 원하면 `--provider pykrx`로 KRX 일봉 조회를 명시적으로 선택할 수 있으며, 이 경우 `KRX_ID`와 `KRX_PW`가 필요합니다.

```bash
python scripts/basebar_reclaim_202608.py
# 결과: output/basebar_202608_reclaim.csv
```

1차 판정 정의: D0 이후 **종가가 기준봉 종가 미만**인 첫날을 눌림 시작으로 삼습니다. 그 뒤 **종가가 기준봉 종가를 초과**한 첫날을 재돌파일로 삼습니다. 재돌파일 **다음 3거래일 중 최소 2거래일**의 종가가 기준봉 종가를 초과하면 `settled`입니다. 재돌파일 자체는 안착 3일에 포함하지 않습니다. `--horizon 60`은 눌림·재돌파를 찾는 최대 거래일 수이며, 안착 확인용 3일은 그 뒤까지 관찰합니다. 같은 종목의 두 번째 재돌파는 이 1차 실험에서 별도로 판정하지 않습니다.

관찰일이 부족하면 `no_pullback_yet`, `no_reclaim_yet`, `awaiting_settlement`로 남습니다. 60거래일을 모두 관찰한 후에만 `no_pullback_within_horizon` 또는 `no_reclaim_within_horizon`으로 확정합니다. 기준봉 당일 종가가 원천 데이터와 다르면 `base_close_mismatch`로 표시해 해당 종목을 판정하지 않습니다. `--through YYYYMMDD`로 조회 종료일을 고정하여 재현할 수 있습니다. 2026년 9월 현재 일부 8월 발생 건에는 60거래일이 아직 지나지 않았으므로 미관측과 실패를 구분해야 합니다.
