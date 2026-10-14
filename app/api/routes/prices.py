from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import PriceQueryServiceDep
from app.api.schemas import ErrorResponse, PriceRead
from app.domain.tickers import Ticker
from app.services.price_query import InvalidPeriodError, PriceNotFoundError

router = APIRouter(prefix="/prices", tags=["prices"])

TickerQuery = Annotated[Ticker, Query(description="Currency ticker")]
UnixTimestampQuery = Annotated[int | None, Query(ge=0, description="UNIX timestamp, inclusive")]


@router.get("", response_model=list[PriceRead], summary="All stored prices for a ticker")
async def get_all_prices(ticker: TickerQuery, service: PriceQueryServiceDep) -> list[PriceRead]:
    prices = await service.get_all(ticker)
    return [PriceRead.model_validate(price) for price in prices]


@router.get(
    "/latest",
    response_model=PriceRead,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    summary="Latest stored price for a ticker",
)
async def get_latest_price(ticker: TickerQuery, service: PriceQueryServiceDep) -> PriceRead:
    try:
        price = await service.get_latest(ticker)
    except PriceNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return PriceRead.model_validate(price)


@router.get(
    "/by-date",
    response_model=list[PriceRead],
    responses={status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse}},
    summary="Prices for a ticker within a time range",
)
async def get_prices_by_date(
    ticker: TickerQuery,
    service: PriceQueryServiceDep,
    date_from: UnixTimestampQuery = None,
    date_to: UnixTimestampQuery = None,
) -> list[PriceRead]:
    try:
        prices = await service.get_by_period(ticker, date_from, date_to)
    except InvalidPeriodError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return [PriceRead.model_validate(price) for price in prices]
