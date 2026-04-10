# auto-trade-stock

> 바이브코딩으로 만든 로컬 웹 서비스 입니다.

AI가 뉴스와 시세를 바탕으로 매매 아이디어를 만들고, 사용자가 직접 승인한 주문만 키움증권 REST API로 전송하는 로컬 전용 프로젝트입니다.

이 프로젝트는 다음 흐름으로 동작합니다.

1. 백엔드가 주기적으로 국내외 뉴스를 수집합니다.
2. OpenAI가 뉴스와 관심 종목 시세를 바탕으로 `buy` / `sell` / `hold` 신호를 생성합니다.
3. 신호는 SQLite에 저장됩니다.
4. 백엔드는 계좌 보유 종목과 비교해 주문 제안서를 만듭니다.
5. 사용자가 프론트엔드에서 제안을 승인하면 그때만 키움증권 API로 실제 주문이 전송됩니다.

직접 승인 전에는 실제 주문이 나가지 않습니다.

## 핵심 특징

- Flask 백엔드 + React/TypeScript 프론트엔드 모노레포
- SQLite 기반 신호, 주문 제안, 주문 로그, 보유 종목, 시스템 로그 저장
- 오전 7시부터 오후 6시까지 뉴스 분석 수행
- 한국 주식시장 시간 기준으로 승인 주문 처리
- 키움증권 REST API 연동
- 다크/라이트 모드 지원 대시보드
- 매도 제안 전 계좌 보유 여부 확인

## 프로젝트 구조

```text
auto-trade-stock/
├─ apps/
│  ├─ backend/
│  │  ├─ app/
│  │  │  ├─ api.py
│  │  │  ├─ config.py
│  │  │  ├─ database.py
│  │  │  ├─ prompts.py
│  │  │  ├─ runtime.py
│  │  │  ├─ schemas.py
│  │  │  └─ services/
│  │  │     ├─ kiwoom_service.py
│  │  │     ├─ market_data_service.py
│  │  │     ├─ market_hours.py
│  │  │     ├─ news_service.py
│  │  │     ├─ openai_service.py
│  │  │     ├─ scheduler.py
│  │  │     └─ trading_engine.py
│  │  ├─ .env.example
│  │  ├─ requirements.txt
│  │  └─ run.py
│  └─ frontend/
│     ├─ src/
│     │  ├─ App.tsx
│     │  ├─ components/dashboard/
│     │  └─ lib/
│     └─ package.json
└─ README.md
```

## 동작 개념

### 1. AI 신호 생성

- 뉴스 수집은 2시간 주기로 수행됩니다.
- 기본적으로 최근 1시간 내 기사 중심으로 분석합니다.
- AI는 점수 `0 ~ 100` 기준으로 방향성을 평가합니다.
  - `0`에 가까울수록 하락 관점
  - `50` 부근일수록 중립 관점
  - `100`에 가까울수록 상승 관점

### 2. 주문 제안 생성

- `buy` 신호는 계좌 총 자산과 노출 제한 비율을 기준으로 제안 수량을 계산합니다.
- `sell` 신호는 현재 키움 계좌에 실제로 보유 중인 종목에 대해서만 제안이 생성됩니다.
- 계좌에 없는 종목은 매도 제안을 만들지 않습니다.
- 거래량이 비정상적으로 급등한 종목은 제안 단계에서 차단될 수 있습니다.

### 3. 사용자 승인 후 주문

- 프론트엔드에서 승인 버튼을 눌러야만 실제 주문이 전송됩니다.
- 승인 시점에 시장이 열려 있어야 합니다.
- 승인 직전에도 보유 수량과 주문 가능 수량을 다시 확인합니다.

## 사전 준비

### 요구 사항

- Python 3.10 이상
- Node.js 18 이상
- npm
- 키움증권 OpenAPI REST 사용 신청
- OpenAI API Key

## 백엔드 설정

### 1. 가상환경 생성 및 패키지 설치

```powershell
cd auto-trade-stock\apps\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 환경 변수 파일 생성

`apps/backend/.env.example`를 복사해서 `apps/backend/.env`를 만듭니다.

```powershell
cd E:\dev\auto-trade-stock\apps\backend
Copy-Item .env.example .env
```

### 3. 필수 환경 변수

최소한 아래 값들은 채워야 합니다.

- `OPENAI_API_KEY`
- `KIWOOM_APP_KEY`
- `KIWOOM_SECRET_KEY`

상황에 따라 같이 확인하면 좋은 값:

- `KIWOOM_ACCOUNT_NO`
- `KIWOOM_USE_MOCK`
- `KIWOOM_ORDER_TYPE_CODE`

### 4. 주요 환경 변수 설명

| 변수 | 설명 |
| --- | --- |
| `OPENAI_API_KEY` | 뉴스 분석용 OpenAI 키 |
| `OPENAI_MODEL` | 분석에 사용할 OpenAI 모델 |
| `OPERATION_START_HOUR` | AI 분석 시작 시각 |
| `OPERATION_END_HOUR` | AI 분석 종료 시각 |
| `NEWS_SCAN_INTERVAL_MINUTES` | 뉴스 재분석 주기 |
| `WATCHLIST_SYMBOLS` | 시세 감시용 종목 목록 |
| `ACCOUNT_MAX_EXPOSURE_RATIO` | 신규 매수 제안 총 노출 한도 |
| `MIN_ACCOUNT_IMPACT_RATIO` | 의미 있는 거래로 볼 최소 비율 |
| `KIWOOM_USE_MOCK` | `true`면 모의투자 API 사용 |
| `KIWOOM_ACCOUNT_NO` | 계좌번호 직접 지정 |
| `KIWOOM_EXCHANGE_CODE` | 기본 거래소 코드, 기본값 `KRX` |
| `KIWOOM_ORDER_TYPE_CODE` | 주문 유형 코드, 기본값 `3`(시장가) |

### 5. JSON 환경 변수

키움증권 REST API는 계좌 환경에 따라 요청 바디가 조금 달라질 수 있어서, 아래 값들을 JSON 문자열로 조정할 수 있게 해두었습니다.

- `KIWOOM_ACCOUNTS_BODY_JSON`
- `KIWOOM_CASH_BODY_JSON`
- `KIWOOM_HOLDINGS_BODY_JSON`
- `KIWOOM_ORDER_BODY_JSON`

기본값 예시:

```env
KIWOOM_ACCOUNTS_BODY_JSON={}
KIWOOM_CASH_BODY_JSON={"acct_no":"{account_no}"}
KIWOOM_HOLDINGS_BODY_JSON={"acct_no":"{account_no}"}
KIWOOM_ORDER_BODY_JSON={"acct_no":"{account_no}"}
```

`{account_no}` 같은 템플릿 값은 백엔드에서 실제 계좌번호로 치환됩니다.

## 백엔드 실행

```powershell
cd auto-trade-stock\apps\backend
.\.venv\Scripts\Activate.ps1
python run.py
```

기본 실행 주소:

- `http://127.0.0.1:5000/health`
- `http://127.0.0.1:5000/api/status`

## 프론트엔드 실행

### 1. 패키지 설치

```powershell
cd E:\dev\auto-trade-stock\apps\frontend
npm install
```

### 2. 개발 서버 실행

```powershell
npm run dev
```

기본 접속 주소:

- `http://127.0.0.1:5173`

프론트엔드는 `/api`와 `/health` 요청을 백엔드로 프록시합니다.

## 화면에서 볼 수 있는 항목

- 승인 대기 주문 제안
- 키움 계좌 보유 종목
- 사용자 승인 후 전송된 주문 기록
- AI 뉴스 분석 신호
- 시스템 로그

## 주요 API

### 상태 및 조회

- `GET /health`
- `GET /api/status`
- `GET /api/signals`
- `GET /api/proposals`
- `GET /api/holdings`
- `GET /api/trades`
- `GET /api/logs`

### 제안 승인/거절

- `POST /api/proposals/<id>/approve`
- `POST /api/proposals/<id>/reject`

### 수동 작업 실행

- `POST /api/tasks/run-cycle`
- `POST /api/tasks/scan-news`
- `POST /api/tasks/sync-holdings`

## SQLite에 저장되는 주요 데이터

- `market_signals`
  - AI가 생성한 매수/매도/관망 신호
- `order_proposals`
  - 사용자 승인을 기다리는 주문 제안
- `broker_holdings`
  - 키움 계좌 보유 종목 스냅샷
- `trade_executions`
  - 승인 후 실제로 전송된 주문 기록
- `system_logs`
  - 동기화, 제안 생성, 승인, 오류 로그

## 운영 시 주의사항

- 이 프로젝트는 로컬 환경 전용입니다.
- AI는 제안만 생성하고, 사용자가 승인해야 주문이 전송됩니다.
- `sell` 제안은 실제 보유 종목에 대해서만 생성됩니다.
- 키움 REST API는 계좌/상품/모의투자 여부에 따라 요청 필드 차이가 있을 수 있으므로, 주문 전 모의투자 환경에서 먼저 확인하는 것을 권장합니다.
- OpenAI 분석은 외부 API를 사용하므로 인터넷 연결이 필요합니다.
- 실제 주문 전송 책임은 사용자에게 있습니다.

## 빠른 시작

```powershell
cd auto-trade-stock\apps\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

```powershell
cd auto-trade-stock\apps\frontend
npm install
npm run dev
```

## 참고 문서

- 키움 REST API 가이드
  - https://openapi.kiwoom.com/guide/apiguide
- 키움 REST API 서비스 안내
  - https://openapi.kiwoom.com/intro/serviceInfo
