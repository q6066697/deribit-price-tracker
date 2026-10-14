from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(examples=["btc_usd"])
    price: Decimal = Field(description="Index price; serialized as a string to keep precision.")
    timestamp: int = Field(description="UNIX timestamp (seconds, UTC)", examples=[1760450400])


class ErrorResponse(BaseModel):
    detail: str
