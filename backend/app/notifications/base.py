from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    async def send(self, event: str, message: str) -> bool:
        """알림 성공 여부를 반환하며 매매 흐름을 예외로 중단하지 않는다."""

