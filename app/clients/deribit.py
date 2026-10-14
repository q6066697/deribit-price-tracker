import json
from decimal import Decimal
from functools import partial
from typing import Any

import aiohttp

from app.domain.tickers import Ticker


class DeribitClientError(Exception):
    """Raised when Deribit is unreachable or returns an unexpected response."""


class DeribitClient:
    """Thin async client for the public Deribit HTTP API."""

    _INDEX_PRICE_PATH = "/public/get_index_price"

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def get_index_price(self, ticker: Ticker) -> Decimal:
        payload = await self._get(self._INDEX_PRICE_PATH, params={"index_name": ticker.value})
        try:
            index_price = payload["result"]["index_price"]
        except (KeyError, TypeError) as error:
            raise DeribitClientError(f"Unexpected response for {ticker}: {payload}") from error
        if isinstance(index_price, bool) or not isinstance(index_price, int | Decimal):
            raise DeribitClientError(f"Index price for {ticker} is not a number: {index_price!r}")
        # An integral price arrives as int, so normalize to Decimal.
        return Decimal(index_price)

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        # parse_float=Decimal keeps the exact price instead of a lossy float.
        decode_json = partial(json.loads, parse_float=Decimal)
        try:
            async with self._session.get(url, params=params) as response:
                payload = await response.json(loads=decode_json, content_type=None)
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError) as error:
            raise DeribitClientError(f"Request to {url} failed: {error!r}") from error

        if response.status != 200 or "error" in payload:
            raise DeribitClientError(
                f"Deribit returned status {response.status}: {payload.get('error', payload)}"
            )
        return payload
