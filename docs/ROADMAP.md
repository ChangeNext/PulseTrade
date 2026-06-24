# Roadmap

## Phase 1 — 현재 MVP

- SIM 주문, 상태 머신, 리스크 정책, 대시보드, 단위 테스트
- KIS와 알림의 교체 가능한 인터페이스

## Phase 2 — 모의투자

- 공식 KIS 인증/REST/WebSocket 구현
- 토큰 캐시와 재연결, 호출 제한, 민감정보 마스킹
- 계좌/미체결/체결 동기화와 DB 복구
- 통합 테스트 및 장애 주입 테스트

## Phase 3 — 제한적 LIVE 검증

- 운영자 확인 흐름, 거래시간/휴장일 검증, 가격 제한
- reconciliation 작업, idempotency key, 주문 취소/정정
- 관측성, 백업, 배포 runbook, 최소 금액 단계적 검증

