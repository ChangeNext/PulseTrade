import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx


class KISConfigurationError(ValueError):
    """필수 KIS 설정이 없거나 형식이 잘못된 경우 발생한다."""


class KISAPIError(RuntimeError):
    """민감한 요청 정보 없이 KIS 오류 코드와 메시지만 전달한다."""

    def __init__(self, message: str, *, code: str = "KIS_API_ERROR", status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class KISResponse:
    data: dict[str, Any]
    headers: httpx.Headers


class KISClient:
    """KIS REST 공통 전송 계층.

    키, 시크릿, 토큰, 계좌번호를 로그나 예외 메시지에 포함하지 않는다.
    """

    def __init__(
        self,
        base_url: str,
        app_key: str,
        app_secret: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token: str | None = None
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self._rate_lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._minimum_interval = 0.5 if "openapivts" in self.base_url.lower() else 0.05

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.app_key and self.app_secret)

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            if not self.base_url:
                raise KISConfigurationError("KIS base URL is not configured")
            self._http_client = httpx.AsyncClient(base_url=self.base_url, timeout=10)
        return self._http_client

    async def close(self) -> None:
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def post_public(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise KISConfigurationError("KIS credentials are not configured")
        async with self._rate_lock:
            await self._wait_for_rate_limit()
            response = await self._client().post(
                path,
                json=payload,
                headers={"content-type": "application/json", "accept": "text/plain"},
            )
            self._last_request_at = monotonic()
        return self._decode_response(response)

    async def request(
        self,
        method: str,
        path: str,
        *,
        tr_id: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        tr_cont: str = "",
    ) -> dict[str, Any]:
        return (await self.request_response(
            method,
            path,
            tr_id=tr_id,
            params=params,
            json=json,
            tr_cont=tr_cont,
        )).data

    async def request_response(
        self,
        method: str,
        path: str,
        *,
        tr_id: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        tr_cont: str = "",
    ) -> KISResponse:
        if not self.configured or not self.access_token:
            raise KISConfigurationError("KIS credentials/token are not configured")
        headers = {
            "content-type": "application/json",
            "accept": "text/plain",
            "charset": "UTF-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "tr_cont": tr_cont,
            "custtype": "P",
        }
        async with self._rate_lock:
            await self._wait_for_rate_limit()
            response = await self._client().request(
                method, path, headers=headers, params=params, json=json
            )
            self._last_request_at = monotonic()
        return KISResponse(data=self._decode_response(response), headers=response.headers)

    async def _wait_for_rate_limit(self) -> None:
        remaining = self._minimum_interval - (monotonic() - self._last_request_at)
        if remaining > 0:
            await asyncio.sleep(remaining)

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise KISAPIError("KIS returned a non-JSON response", status_code=response.status_code) from exc

        if response.is_error:
            raise KISAPIError(
                str(payload.get("msg1") or "KIS HTTP request failed"),
                code=str(payload.get("msg_cd") or "KIS_HTTP_ERROR"),
                status_code=response.status_code,
            )
        if "rt_cd" in payload and str(payload["rt_cd"]) != "0":
            raise KISAPIError(
                str(payload.get("msg1") or "KIS business request failed"),
                code=str(payload.get("msg_cd") or "KIS_BUSINESS_ERROR"),
            )
        return payload
