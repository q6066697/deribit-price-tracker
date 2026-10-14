import pytest

from app.domain.tickers import Ticker
from app.repositories.prices import PriceRepository
from app.services.price_query import InvalidPeriodError, PriceNotFoundError, PriceQueryService


async def test_get_latest_raises_when_no_prices(db_session):
    service = PriceQueryService(PriceRepository(db_session))

    with pytest.raises(PriceNotFoundError):
        await service.get_latest(Ticker.BTC_USD)


async def test_get_by_period_rejects_inverted_range(db_session):
    service = PriceQueryService(PriceRepository(db_session))

    with pytest.raises(InvalidPeriodError):
        await service.get_by_period(Ticker.BTC_USD, date_from=200, date_to=100)
