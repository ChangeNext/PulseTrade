# ORB + VWAP + Volume Strategy

초기 구현은 다음 조건이 모두 참일 때 BUY 신호만 생성한다.

- 현재가가 Opening Range 고가보다 높음
- 현재가가 VWAP보다 높음
- 현재 1분 거래량이 최근 평균의 기본 2배보다 큼
- 이미 보유 중이 아님
- 같은 종목의 미체결 주문이 없음

Opening Range 집계 구간, 장 상태, 호가 단위, 거래정지/VI 처리는 실제 전략 운영 전에 추가해야 한다. 생성된 신호는 주문이 아니며 ExecutionEngine과 RiskManager를 우회할 수 없다.

