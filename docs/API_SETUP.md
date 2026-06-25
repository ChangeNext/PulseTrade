# KIS API Setup

이 문서는 안전한 연결 순서를 정의합니다. endpoint, header, TR ID, 요청·응답 필드는 사용 시점의 한국투자증권 공식 Open API 문서와 공식 샘플 저장소에서 확인합니다.

## 현재 구현

- 실전/모의 Access Token 발급과 메모리 캐시
- 국내주식 잔고조회
- 예수금, 총평가금액, 미실현손익 매핑
- 보유종목, 평균단가, 현재가, 평가손익, 수익률 매핑
- 연속조회와 짧은 응답 캐시
- 모의투자 지정가 현금 매수·매도와 주문가능금액 조회
- 당일 주문·부분체결·체결 동기화와 미체결 전량 취소
- WebSocket 체결가 구독과 장중 1분봉 백필

## 설정 체크리스트

1. 공식 포털에서 앱 키/시크릿을 발급하고 `backend/.env`에만 저장합니다.
2. 계좌번호 앞 8자리는 `KIS_ACCOUNT_NUMBER`, 뒤 2자리는 `KIS_ACCOUNT_PRODUCT_CODE`에 입력합니다.
3. 실전 REST URL과 모의투자 REST URL을 혼용하지 않습니다.
4. 앱 키도 서버 환경과 일치하는 키를 사용합니다.
5. HTTP 원문을 저장할 때 토큰, 앱 키, 시크릿, 계좌번호를 마스킹합니다.
6. 운영 전 `market.py`, `order.py`, `websocket.py`의 TR ID와 필드를 최신 공식 샘플과 다시 대조합니다.
7. PAPER 주문도 계좌·주문·손익 동기화가 모두 성공하기 전에는 활성화하지 않습니다.

## 읽기 전용 연결 확인

다음 명령은 잔액이나 민감값을 출력하지 않고 연결 성공 여부와 보유종목 수만 표시합니다.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\check_kis_account.py
```

실전 주문 전에는 다음 사전점검을 먼저 실행합니다. 이 명령은 주문을 전송하지 않고 토큰, 계좌조회, 현재가, 주문가능금액 조회까지만 확인합니다.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\check_kis_live_preflight.py
```

`KIS_LIVE_PREFLIGHT_OK`가 나오기 전에는 `ENABLE_LIVE_TRADING=true`로 전환하지 않습니다.

공식 확인 전 남은 TODO를 임의 값으로 교체하지 않습니다.
