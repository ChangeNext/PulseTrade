import httpx

from app.notifications.base import Notifier
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send(self, event: str, message: str) -> bool:
        if not self.configured:
            logger.info("Telegram disabled: %s - %s", event, message)
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url,
                    json={"chat_id": self.chat_id, "text": f"[PulseTrade:{event}] {message}"},
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            logger.exception("Telegram notification failed")
            return False

