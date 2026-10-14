from decimal import Decimal

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from app.clients.deribit import DeribitClient, DeribitClientError
from app.domain.tickers import Ticker


class FakeDeribit:
    """Local HTTP server that imitates Deribit's /public/get_index_price endpoint."""

    def __init__(self) -> None:
        self.status = 200
        self.body = '{"jsonrpc": "2.0", "result": {"index_price": 67123.12345678}}'
        self.received_params: dict[str, str] = {}

    async def handle(self, request: web.Request) -> web.Response:
        self.received_params = dict(request.query)
        return web.Response(status=self.status, text=self.body, content_type="application/json")


@pytest.fixture
def fake_deribit() -> FakeDeribit:
    return FakeDeribit()


@pytest.fixture
async def client(fake_deribit):
    app = web.Application()
    app.router.add_get("/api/v2/public/get_index_price", fake_deribit.handle)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        yield DeribitClient(session, str(server.make_url("/api/v2")))


async def test_returns_exact_decimal_price(client):
    price = await client.get_index_price(Ticker.BTC_USD)

    assert price == Decimal("67123.12345678")


async def test_sends_ticker_as_index_name(client, fake_deribit):
    fake_deribit.body = '{"result": {"index_price": 2500}}'

    price = await client.get_index_price(Ticker.ETH_USD)

    assert price == Decimal(2500)
    assert fake_deribit.received_params == {"index_name": "eth_usd"}


async def test_raises_on_api_error(client, fake_deribit):
    fake_deribit.status = 400
    fake_deribit.body = '{"error": {"code": -32602, "message": "Invalid params"}}'

    with pytest.raises(DeribitClientError, match="Invalid params"):
        await client.get_index_price(Ticker.BTC_USD)


@pytest.mark.parametrize(
    "body",
    ['{"result": {}}', '{"result": {"index_price": "abc"}}', "not json"],
)
async def test_raises_on_unexpected_payload(client, fake_deribit, body):
    fake_deribit.body = body

    with pytest.raises(DeribitClientError):
        await client.get_index_price(Ticker.BTC_USD)


async def test_raises_on_network_error():
    async with aiohttp.ClientSession() as session:
        client = DeribitClient(session, "http://127.0.0.1:1/api/v2")

        with pytest.raises(DeribitClientError, match="failed"):
            await client.get_index_price(Ticker.BTC_USD)
