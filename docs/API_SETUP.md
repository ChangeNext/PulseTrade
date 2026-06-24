# KIS API Setup

이 문서는 안전한 연결 순서를 정의합니다. endpoint, header, TR ID, 요청·응답 필드는 사용 시점의 한국투자증권 공식 Open API 문서와 공식 샘플 저장소에서 확인합니다.

## 현재 구현

- 실전/모의 Access Token 발급과 메모리 캐시
- 국내주식 잔고조회
- 예수금, 총평가금액, 미실현손익 매핑
- 보유종목, 평균단가, 현재가, 평가손익, 수익률 매핑
- 연속조회와 짧은 응답 캐시
- 주문 API와 분리된 읽기 전용 연결

## 설정 체크리스트

1. 공식 포털에서 앱 키/시크릿을 발급하고 `backend/.env`에만 저장합니다.
2. 계좌번호 앞 8자리는 `KIS_ACCOUNT_NUMBER`, 뒤 2자리는 `KIS_ACCOUNT_PRODUCT_CODE`에 입력합니다.
3. 실전 REST URL과 모의투자 REST URL을 혼용하지 않습니다.
4. 앱 키도 서버 환경과 일치하는 키를 사용합니다.
5. HTTP 원문을 저장할 때 토큰, 앱 키, 시크릿, 계좌번호를 마스킹합니다.
6. `market.py`, `order.py`, `websocket.py`는 구현 시점의 공식 문서로 별도 검증합니다.
7. 실제 주문은 계좌 조회 검증만으로 활성화하지 않습니다.

## 읽기 전용 연결 확인

다음 명령은 잔액이나 민감값을 출력하지 않고 연결 성공 여부와 보유종목 수만 표시합니다.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\check_kis_account.py
```

공식 확인 전 남은 TODO를 임의 값으로 교체하지 않습니다.
