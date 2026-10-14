from enum import StrEnum


class Ticker(StrEnum):
    """Currency tickers supported by the service (Deribit index names)."""

    BTC_USD = "btc_usd"
    ETH_USD = "eth_usd"
