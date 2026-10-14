from decimal import Decimal

import pytest

from app.domain.prices import PriceSnapshot
from app.domain.tickers import Ticker
from app.repositories.prices import PriceRepository


@pytest.fixture
async def repository(db_session):
    repository = PriceRepository(db_session)
    await repository.add_many(
        [
            PriceSnapshot(Ticker.BTC_USD, Decimal("100"), timestamp=1000),
            PriceSnapshot(Ticker.BTC_USD, Decimal("300"), timestamp=3000),
            PriceSnapshot(Ticker.BTC_USD, Decimal("200"), timestamp=2000),
            PriceSnapshot(Ticker.ETH_USD, Decimal("10"), timestamp=5000),
        ]
    )
    return repository


async def test_get_all_filters_by_ticker_and_sorts_by_time(repository):
    prices = await repository.get_all(Ticker.BTC_USD)

    assert [p.timestamp for p in prices] == [1000, 2000, 3000]


async def test_get_latest_returns_most_recent(repository):
    latest = await repository.get_latest(Ticker.BTC_USD)

    assert latest.timestamp == 3000
    assert latest.price == Decimal("300")


@pytest.mark.parametrize(
    ("date_from", "date_to", "expected"),
    [
        (2000, None, [2000, 3000]),
        (None, 2000, [1000, 2000]),
        (1500, 2500, [2000]),
        (None, None, [1000, 2000, 3000]),
    ],
)
async def test_get_by_period_bounds_are_inclusive(repository, date_from, date_to, expected):
    prices = await repository.get_by_period(Ticker.BTC_USD, date_from, date_to)

    assert [p.timestamp for p in prices] == expected
