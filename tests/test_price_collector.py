from decimal import Decimal

from app.domain.tickers import Ticker
from app.repositories.prices import PriceRepository
from app.services.price_collector import PriceCollector

FIXED_TIME = 1_760_450_400.9


class FakePriceProvider:
    def __init__(self, prices: dict[Ticker, Decimal], failing: set[Ticker] = frozenset()):
        self._prices = prices
        self._failing = failing

    async def get_index_price(self, ticker: Ticker) -> Decimal:
        if ticker in self._failing:
            raise RuntimeError("exchange is down")
        return self._prices[ticker]


async def test_collects_and_saves_all_tickers(db_session):
    provider = FakePriceProvider(
        {Ticker.BTC_USD: Decimal("67000.5"), Ticker.ETH_USD: Decimal("2500")}
    )
    repository = PriceRepository(db_session)
    collector = PriceCollector(provider, repository, clock=lambda: FIXED_TIME)

    snapshots = await collector.collect(Ticker)

    assert {s.ticker for s in snapshots} == {Ticker.BTC_USD, Ticker.ETH_USD}
    assert all(s.timestamp == 1_760_450_400 for s in snapshots)
    stored = await repository.get_latest(Ticker.BTC_USD)
    assert stored.price == Decimal("67000.5")


async def test_failure_of_one_ticker_does_not_block_others(db_session):
    provider = FakePriceProvider({Ticker.ETH_USD: Decimal("2500")}, failing={Ticker.BTC_USD})
    repository = PriceRepository(db_session)
    collector = PriceCollector(provider, repository, clock=lambda: FIXED_TIME)

    snapshots = await collector.collect(Ticker)

    assert [s.ticker for s in snapshots] == [Ticker.ETH_USD]
    assert await repository.get_latest(Ticker.BTC_USD) is None
    assert await repository.get_latest(Ticker.ETH_USD) is not None
