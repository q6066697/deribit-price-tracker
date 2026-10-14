from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prices import PriceRepository
from app.services.price_query import PriceQueryService


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_price_query_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceQueryService:
    return PriceQueryService(PriceRepository(session))


PriceQueryServiceDep = Annotated[PriceQueryService, Depends(get_price_query_service)]
