# PulseTrade

한국투자증권 Open API 연동을 전제로 한 국내주식 단타 자동매매 시스템의 안전 중심 MVP 스캐폴딩입니다. 이 프로젝트는 수익을 보장하지 않으며 기본 실행 모드는 브로커에 주문을 보내지 않는 `SIM`입니다.

## 한 번에 실행

프로젝트 루트에서 다음 명령을 실행하면 백엔드와 프론트엔드가 함께 시작됩니다. 최초 실행 시 필요한 의존성도 자동 설치합니다.

```powershell
cd C:\code\Project\PulseTrade
.\dev.cmd
```

- 대시보드: `http://127.0.0.1:5173`
- API 문서: `http://127.0.0.1:8000/docs`
- 종료: 실행 터미널에서 `Ctrl+C`

WSL/Linux에서는 다음 명령을 사용합니다.

```bash
./dev.sh
```

## 현재 구현 범위

- FastAPI + asyncio 기반 API와 비동기 SQLAlchemy/SQLite
- `SIM` 로컬 주문과 KIS `PAPER` 모의투자 주문의 명확한 분리
- 주문 상태 머신과 보수적인 RiskManager
- 수동 SIM 주문 API, 긴급 정지, 자동매매 ON/OFF
- Telegram 알림 어댑터와 Kakao 확장 인터페이스
- KIS 실전/모의 Access Token과 국내주식 잔고·포지션 읽기 전용 조회
- KIS 지정가 매수·매도, 당일 주문·체결 동기화와 미체결 취소
- 멱등 주문, 부분체결, 전송 결과 불명 상태 및 재시작 복구
- KIS 실시간 체결가와 1분봉 백필 기반 ORB/VWAP/거래량 자동주문
- 고정 손절·익절 지정가 자동 청산
- React/TypeScript/Vite 대시보드
- 리스크, 상태 머신, 전략 단위 테스트

> LIVE 주문 서비스는 의도적으로 주입되지 않으며 모든 실계좌 주문이 거부됩니다. PAPER 주문은 반드시 KIS 모의투자 URL과 모의 앱 키를 사용해야 합니다.

## Backend 실행

Python 3.11 이상을 권장합니다.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

테스트:

```powershell
cd backend
python -m pytest -q
```

민감값이나 잔액을 출력하지 않고 KIS 계좌 연결만 점검하려면:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\check_kis_account.py
```

## Frontend 실행

Node.js 20 이상을 권장합니다.

```powershell
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:5173`을 엽니다. 다른 API 주소를 사용할 때는 `VITE_API_BASE_URL`을 지정합니다.

## PAPER 주문 활성화

1. `TRADING_MODE=PAPER`
2. KIS 모의투자 앱 키와 모의계좌 설정
3. `KIS_BASE_URL`이 `openapivts.koreainvestment.com`을 사용
4. 잔고·당일 주문·손익 동기화 성공
5. 수동 주문 요청에 고유한 `Idempotency-Key` 헤더 사용

자동매매에는 `STRATEGY_SYMBOLS`와 WebSocket URL도 필요합니다. 서버 재시작 시 이전 희망 상태를 복원하지만 동기화와 전략 백필이 완료되기 전에는 주문하지 않습니다.

감시 종목은 `backend/.env`의 쉼표 구분 6자리 코드로 설정합니다.

```dotenv
STRATEGY_SYMBOLS=005930,000660
```

변경 후 서버를 재시작해야 적용됩니다. 초기 기본값은 `005930`입니다.

SIM은 최우선호가와 잔량을 이용해 부분체결하며 150ms 지연, 수수료·매도세금, 미체결 재호가를 반영합니다. 전략 주문은 기본 3초 후 취소·재호가하고 최대 30분 보유 또는 15:15에 지정가 청산합니다.

비용과 슬리피지를 포함한 CSV 백테스트:

```bash
cd backend
./.venv/bin/python scripts/backtest_strategy.py data.csv --slippage-bps 5
```

CSV 필수 열은 `timestamp,symbol,close,high,low,volume,best_ask,best_bid,ask_quantity,bid_quantity,trade_strength`입니다.
현재 백테스트는 자본 혼합을 방지하기 위해 파일당 한 종목만 허용합니다.

## LIVE 전환 조건

현재 LIVE 어댑터가 연결되지 않아 실제 주문은 항상 거부됩니다. 이후 별도 단계에서 구현하더라도 다음 조건을 모두 만족해야 합니다.

1. `.env`의 `TRADING_MODE=LIVE`
2. `ENABLE_LIVE_TRADING=true`
3. 요청마다 `live_confirmation`이 설정된 확인 문구와 정확히 일치
4. RiskManager 승인
5. 공식 KIS 문서로 검증한 주문 서비스가 실행 엔진에 주입됨
6. 시작 시 잔고·포지션·미체결 주문 동기화 완료

운영 전에는 모의투자 계좌, 주문 단위 테스트, 장애 복구 테스트를 별도로 수행해야 합니다.

## 구조

요청한 디렉터리 구조를 따르며, 핵심 설명은 [ARCHITECTURE.md](docs/ARCHITECTURE.md), 리스크 기본값은 [RISK_POLICY.md](docs/RISK_POLICY.md), KIS 연동 체크리스트는 [API_SETUP.md](docs/API_SETUP.md)를 참고하세요.
