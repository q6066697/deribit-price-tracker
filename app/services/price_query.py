from app.db.models import Price
from app.domain.tickers import Ticker
from app.repositories.prices import PriceRepository


class PriceNotFoundError(Exception):
    def __init__(self, ticker: Ticker) -> None:
        super().__init__(f"No prices stored for {ticker}")
        self.ticker = ticker


class InvalidPeriodError(Exception):
    pass


class PriceQueryService:
    """Read-side business logic used by the HTTP API."""

    def __init__(self, repository: PriceRepository) -> None:
        self._repository = repository

    async def get_all(self, ticker: Ticker) -> list[Price]:
        return await self._repository.get_all(ticker)

    async def get_latest(self, ticker: Ticker) -> Price:
        price = await self._repository.get_latest(ticker)
        if price is None:
            raise PriceNotFoundError(ticker)
        return price

    async def get_by_period(
        self, ticker: Ticker, date_from: int | None, date_to: int | None
    ) -> list[Price]:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise InvalidPeriodError("date_from must be less than or equal to date_to")
        return await self._repository.get_by_period(ticker, date_from, date_to)
