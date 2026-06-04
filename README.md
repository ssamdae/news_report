# Stock Research System

Python 기반 한국 주식 리서치 자동화 시스템입니다.

Oracle Cloud Ubuntu 24.04 환경에서 한국 주식 시장의 500억봉 조건 탐지 시스템을 개발하기 위한 초기 프로젝트 구조입니다.

## 목적

최종 목표는 한국 주식 중 사용자가 정의한 500억봉 조건을 만족하는 종목을 자동 탐색하고, 이후 뉴스, 공시, AI 분석, PDF 리포트, Streamlit 대시보드까지 확장하는 투자 리서치 플랫폼 구축입니다.

현재 단계에서는 실제 기능을 구현하지 않고, 프로젝트 초기 구조와 설정 파일만 준비합니다.

## 운영 환경

- Oracle Cloud VM
- OS: Ubuntu 24.04 LTS
- Python: 3.12
- Database: PostgreSQL 16
- Dashboard: Streamlit
- Version control: Git

## 현재 생성 범위

- 폴더 구조
- `requirements.txt`
- `.env.example`
- `README.md`
- `database/schema.sql`

## 아직 구현하지 않는 항목

- 실제 주가 데이터 수집
- 500억봉 탐지 로직
- DB 저장 로직
- Streamlit 화면
- 뉴스 수집
- DART 공시 수집
- AI 분석
- PDF 리포트 생성
- Docker 구성

## 폴더 구조

```text
stock-research-system/
├── collector/
├── dashboard/
├── database/
├── filter/
├── .env.example
├── README.md
├── main.py
├── requirements.txt
└── database/schema.sql
```

## 초기 설정

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 데이터베이스 스키마

초기 스키마는 `database/schema.sql`에 있습니다.

포함 테이블:

- `stock_master`
- `daily_price`
- `signal_event`
- `job_run`

## Docker

이 프로젝트 초기 구조에서는 Docker를 사용하지 않습니다.
