from dataclasses import dataclass
from decimal import Decimal

from app.domain.tickers import Ticker


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    """A single index price observation, independent of storage and transport."""

    ticker: Ticker
    price: Decimal
    timestamp: int
