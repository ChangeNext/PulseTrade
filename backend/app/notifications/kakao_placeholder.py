from app.notifications.base import Notifier


class KakaoNotifierPlaceholder(Notifier):
    async def send(self, event: str, message: str) -> bool:
        # TODO: 카카오 공식 메시지 API의 인증/동의 정책 확정 후 구현한다.
        return False

