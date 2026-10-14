from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_price_query_service
from app.db.models import Price
from app.domain.tickers import Ticker
from app.main import create_app
from app.services.price_query import InvalidPeriodError, PriceNotFoundError

BTC_PRICES = [
    Price(ticker="btc_usd", price=Decimal("100.5"), timestamp=1000),
    Price(ticker="btc_usd", price=Decimal("200"), timestamp=2000),
]


class FakePriceQueryService:
    async def get_all(self, ticker: Ticker) -> list[Price]:
        return BTC_PRICES if ticker is Ticker.BTC_USD else []

    async def get_latest(self, ticker: Ticker) -> Price:
        if ticker is not Ticker.BTC_USD:
            raise PriceNotFoundError(ticker)
        return BTC_PRICES[-1]

    async def get_by_period(self, ticker, date_from, date_to) -> list[Price]:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise InvalidPeriodError("date_from must be less than or equal to date_to")
        return [p for p in BTC_PRICES if date_from is None or p.timestamp >= date_from]


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_price_query_service] = FakePriceQueryService
    # No "with": lifespan (real DB engine) is not started for these API-level tests.
    return TestClient(app)


def test_get_all_prices(client):
    response = client.get("/api/v1/prices", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json() == [
        {"ticker": "btc_usd", "price": "100.5", "timestamp": 1000},
        {"ticker": "btc_usd", "price": "200", "timestamp": 2000},
    ]


def test_get_latest_price(client):
    response = client.get("/api/v1/prices/latest", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json()["timestamp"] == 2000


def test_get_latest_price_returns_404_when_empty(client):
    response = client.get("/api/v1/prices/latest", params={"ticker": "eth_usd"})

    assert response.status_code == 404


def test_get_prices_by_date(client):
    response = client.get("/api/v1/prices/by-date", params={"ticker": "btc_usd", "date_from": 1500})

    assert response.status_code == 200
    assert [p["timestamp"] for p in response.json()] == [2000]


def test_get_prices_by_date_rejects_inverted_period(client):
    response = client.get(
        "/api/v1/prices/by-date", params={"ticker": "btc_usd", "date_from": 10, "date_to": 5}
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "path", ["/api/v1/prices", "/api/v1/prices/latest", "/api/v1/prices/by-date"]
)
def test_ticker_is_required(client, path):
    assert client.get(path).status_code == 422


def test_unknown_ticker_is_rejected(client):
    response = client.get("/api/v1/prices", params={"ticker": "doge_usd"})

    assert response.status_code == 422
