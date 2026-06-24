from decimal import Decimal


class PositionManager:
    def __init__(self) -> None:
        self._amounts: dict[str, Decimal] = {}

    def replace_from_broker(self, amounts: dict[str, Decimal]) -> None:
        """앱 재시작 시 브로커 조회 결과를 내부 상태의 기준으로 삼는다."""
        self._amounts = dict(amounts)

    def snapshot(self) -> dict[str, Decimal]:
        return dict(self._amounts)

