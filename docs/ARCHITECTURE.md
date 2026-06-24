# Architecture

## 실행 흐름

`Strategy/Manual API → ExecutionEngine → RiskManager → SIM 또는 KISOrderService → OrderStateMachine → DB/Notifier`

- 전략은 `StrategySignal`만 생성한다. 자동 실행 여부는 실행 엔진의 별도 옵션이다.
- 실행 엔진은 모든 주문을 RiskManager에 먼저 전달한다.
- `SIM`/`PAPER`는 브로커 네트워크 호출 없이 `ORDER_SENT`까지 전이한다.
- LIVE는 설정 플래그, 요청 확인 문구, 리스크 승인, 주입된 KIS 주문 서비스가 모두 필요하다.
- DB URL만 변경할 수 있게 SQLAlchemy 경계를 유지해 PostgreSQL 확장을 가능하게 했다.

## 재시작 동기화 설계

운영 버전의 lifespan 시작 단계는 자동매매를 비활성화한 상태로 KIS 잔고와 당일 주문/체결/미체결을 조회해야 한다. 조회 결과를 `PositionManager.replace_from_broker()`와 주문 저장소에 반영하고 불일치가 없을 때만 자동매매 활성화를 허용한다. 동기화 실패, API 단절, WebSocket 단절 시 자동매매를 중단한다.

## 로그

`EventLog`는 API 요청/응답, 전략 신호, 리스크 차단, 주문, 체결, 오류 이벤트를 분류해 저장할 공통 테이블이다. MVP 수동 주문은 주문 레코드와 주문/리스크 이벤트를 저장한다. KIS 구현 시 민감한 header와 토큰을 반드시 마스킹한다.

