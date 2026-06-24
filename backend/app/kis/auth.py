import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.kis.client import KISAPIError, KISClient

KST = timezone(timedelta(hours=9), name="KST")


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_at: datetime


class KISAuthService:
    """공식 `/oauth2/tokenP` 토큰을 메모리에서 안전하게 재사용한다."""

    def __init__(self, client: KISClient) -> None:
        self.client = client
        self._token: AccessToken | None = None
        self._lock = asyncio.Lock()

    async def ensure_access_token(self) -> AccessToken:
        if self._is_valid(self._token):
            return self._token  # type: ignore[return-value]
        async with self._lock:
            if self._is_valid(self._token):
                return self._token  # type: ignore[return-value]
            return await self.issue_access_token()

    async def issue_access_token(self) -> AccessToken:
        payload = await self.client.post_public(
            "/oauth2/tokenP",
            {
                "grant_type": "client_credentials",
                "appkey": self.client.app_key,
                "appsecret": self.client.app_secret,
            },
        )
        value = str(payload.get("access_token") or "")
        if not value:
            raise KISAPIError("KIS token response did not include access_token", code="TOKEN_MISSING")
        expires_at = self._parse_expiry(payload)
        token = AccessToken(value=value, expires_at=expires_at)
        self._token = token
        self.client.access_token = value
        return token

    @staticmethod
    def _is_valid(token: AccessToken | None) -> bool:
        return bool(token and token.expires_at > datetime.now(UTC) + timedelta(minutes=5))

    @staticmethod
    def _parse_expiry(payload: dict) -> datetime:
        official_expiry = payload.get("access_token_token_expired")
        if official_expiry:
            parsed = datetime.strptime(str(official_expiry), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
            return parsed.astimezone(UTC)
        expires_in = int(payload.get("expires_in") or 86_400)
        return datetime.now(UTC) + timedelta(seconds=expires_in)
