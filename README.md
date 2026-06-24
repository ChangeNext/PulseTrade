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

## 현재 구현 범위

- FastAPI + asyncio 기반 API와 비동기 SQLAlchemy/SQLite
- `SIM`/`PAPER` 기본 모드, LIVE 설정·요청 이중 확인
- 주문 상태 머신과 보수적인 RiskManager
- 수동 SIM 주문 API, 긴급 정지, 자동매매 ON/OFF
- Telegram 알림 어댑터와 Kakao 확장 인터페이스
- KIS 실전/모의 Access Token과 국내주식 잔고·포지션 읽기 전용 조회
- KIS 시세·주문·WebSocket 경계(공식 값 확인용 TODO)
- ORB/VWAP/거래량 전략의 SIGNAL 전용 구현
- React/TypeScript/Vite 대시보드
- 리스크, 상태 머신, 전략 단위 테스트

> 계좌 조회는 KIS 공식 샘플의 `inquire-balance` 규격을 사용합니다. LIVE 주문 서비스는 여전히 실행 엔진에 주입되지 않으므로 실제 주문은 전송되지 않습니다.

## Backend 실행

Python 3.11 이상을 권장합니다.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
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

## LIVE 전환 조건

현재 스캐폴딩에서는 LIVE 어댑터가 연결되지 않아 실제 주문이 실행되지 않습니다. 이후 구현하더라도 다음 조건을 모두 만족해야 합니다.

1. `.env`의 `TRADING_MODE=LIVE`
2. `ENABLE_LIVE_TRADING=true`
3. 요청마다 `live_confirmation`이 설정된 확인 문구와 정확히 일치
4. RiskManager 승인
5. 공식 KIS 문서로 검증한 주문 서비스가 실행 엔진에 주입됨
6. 시작 시 잔고·포지션·미체결 주문 동기화 완료

운영 전에는 모의투자 계좌, 주문 단위 테스트, 장애 복구 테스트를 별도로 수행해야 합니다.

## 구조

요청한 디렉터리 구조를 따르며, 핵심 설명은 [ARCHITECTURE.md](docs/ARCHITECTURE.md), 리스크 기본값은 [RISK_POLICY.md](docs/RISK_POLICY.md), KIS 연동 체크리스트는 [API_SETUP.md](docs/API_SETUP.md)를 참고하세요.
