import asyncio
import logging
import time
from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import Protocol

from app.domain.prices import PriceSnapshot
from app.domain.tickers import Ticker
from app.repositories.prices import PriceRepository

logger = logging.getLogger(__name__)


class IndexPriceProvider(Protocol):
    """Anything that can return the current index price (DeribitClient, a test fake, ...)."""

    async def get_index_price(self, ticker: Ticker) -> Decimal: ...


class PriceCollector:
    """Fetches current index prices for the given tickers and stores them."""

    def __init__(
        self,
        provider: IndexPriceProvider,
        repository: PriceRepository,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._clock = clock

    async def collect(self, tickers: Iterable[Ticker]) -> list[PriceSnapshot]:
        tickers = list(tickers)
        # One timestamp per run, so prices fetched together share the same moment.
        timestamp = int(self._clock())
        results = await asyncio.gather(
            *(self._provider.get_index_price(ticker) for ticker in tickers),
            return_exceptions=True,
        )

        snapshots: list[PriceSnapshot] = []
        for ticker, result in zip(tickers, results, strict=True):
            if isinstance(result, Exception):
                # A failure for one ticker must not block saving the others.
                logger.error("Failed to fetch index price for %s: %s", ticker, result)
                continue
            snapshots.append(PriceSnapshot(ticker=ticker, price=result, timestamp=timestamp))

        if snapshots:
            await self._repository.add_many(snapshots)
        return snapshots
