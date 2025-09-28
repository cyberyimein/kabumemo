from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, FieldValidationInfo, field_validator, model_validator


class Market(str, Enum):
    JP = "JP"
    US = "US"


class Currency(str, Enum):
    JPY = "JPY"
    USD = "USD"


class TaxStatus(str, Enum):
    YES = "Y"
    NO = "N"


class FundingGroup(BaseModel):
    name: str = Field(..., min_length=1)
    currency: Currency
    initial_amount: float = Field(..., ge=0.0)
    notes: Optional[str] = None


class FundingGroupUpdate(BaseModel):
    currency: Optional[Currency] = None
    initial_amount: Optional[float] = Field(default=None, ge=0.0)
    notes: Optional[str] = None


class TransactionBase(BaseModel):
    trade_date: date = Field(default_factory=date.today)
    symbol: str = Field(..., min_length=1)
    quantity: float
    gross_amount: float = Field(..., gt=0.0, description="Total cash outlay or proceeds")
    funding_group: str = Field(..., min_length=1)
    cash_currency: Currency
    market: Market
    taxed: TaxStatus = TaxStatus.YES
    memo: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_nonzero(cls, value: float) -> float:
        if value == 0:
            raise ValueError("quantity must not be zero")
        return value


class TransactionCreate(TransactionBase):
    taxed: TaxStatus | None = None

    @model_validator(mode="after")
    def default_tax_status(self) -> TransactionCreate:
        if self.taxed is None:
            self.taxed = TaxStatus.YES if self.quantity > 0 else TaxStatus.NO
        return self


class Transaction(TransactionBase):
    id: str


class TransactionUpdate(TransactionBase):
    pass


class Position(BaseModel):
    symbol: str
    quantity: float
    average_cost: float
    realized_pl: float
    market: Market


class FundSnapshot(BaseModel):
    name: str
    currency: Currency
    initial_amount: float
    cash_balance: float
    holding_cost: float
    current_total: float
    total_pl: float


class TaxSettlementRequest(BaseModel):
    transaction_id: str
    funding_group: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0.0)
    currency: Currency
    exchange_rate: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="JPY per USD when paying USD taxes in JPY",
    )

    @field_validator("exchange_rate", mode="before")
    def exchange_rate_required_for_usd(
        cls, value: Optional[float], info: FieldValidationInfo
    ) -> Optional[float]:
        currency = info.data.get("currency")
        if currency == Currency.USD and value is None:
            raise ValueError("exchange_rate is required when currency is USD")
        return value


class TaxSettlementResponse(BaseModel):
    transaction_id: str
    amount_paid: float
    currency: Currency
    jpy_equivalent: float
    new_tax_status: TaxStatus


class HealthResponse(BaseModel):
    status: str
