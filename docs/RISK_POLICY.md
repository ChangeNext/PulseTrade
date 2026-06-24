# Risk Policy

MVP 기본값은 테스트 목적의 보수적인 한도다.

| 정책 | 기본값 | 차단 코드 |
|---|---:|---|
| 1회 최대 주문금액 | 100,000원 | `MAX_ORDER_AMOUNT_EXCEEDED` |
| 하루 최대 손실 | 50,000원 | `MAX_DAILY_LOSS_REACHED` |
| 하루 최대 주문 횟수 | 5회 | `MAX_DAILY_ORDERS_REACHED` |
| 종목별 최대 보유금액 | 300,000원 | `MAX_POSITION_AMOUNT_EXCEEDED` |

중복 주문, 같은 종목 미체결 매수, API 단절, WebSocket 단절, 긴급 정지는 금액과 관계없이 주문을 차단한다. 한도 변경은 `.env`에서만 수행하며 주문 직전에 항상 다시 평가한다.

긴급 정지를 활성화하면 자동매매가 즉시 OFF 된다. 해제 후 자동매매는 자동 복구되지 않으며 사용자가 별도로 ON 해야 한다.

