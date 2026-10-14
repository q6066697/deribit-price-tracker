from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Price
from app.domain.prices import PriceSnapshot
from app.domain.tickers import Ticker


class PriceRepository:
    """Data access for the prices table. Transaction control stays with the caller."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, snapshots: Sequence[PriceSnapshot]) -> None:
        self._session.add_all(
            Price(ticker=s.ticker.value, price=s.price, timestamp=s.timestamp) for s in snapshots
        )
        await self._session.flush()

    async def get_all(self, ticker: Ticker) -> list[Price]:
        query = select(Price).where(Price.ticker == ticker.value).order_by(Price.timestamp)
        return list(await self._session.scalars(query))

    async def get_latest(self, ticker: Ticker) -> Price | None:
        query = (
            select(Price)
            .where(Price.ticker == ticker.value)
            .order_by(Price.timestamp.desc(), Price.id.desc())
            .limit(1)
        )
        return await self._session.scalar(query)

    async def get_by_period(
        self, ticker: Ticker, date_from: int | None, date_to: int | None
    ) -> list[Price]:
        query = select(Price).where(Price.ticker == ticker.value)
        if date_from is not None:
            query = query.where(Price.timestamp >= date_from)
        if date_to is not None:
            query = query.where(Price.timestamp <= date_to)
        return list(await self._session.scalars(query.order_by(Price.timestamp)))
