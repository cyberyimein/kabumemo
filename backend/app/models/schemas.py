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


class PositionBreakdown(BaseModel):
    currency: Currency
    quantity: float
    average_cost: float
    realized_pl: float


class Position(BaseModel):
    symbol: str
    market: Market
    breakdown: list[PositionBreakdown]


class FundSnapshot(BaseModel):
    name: str
    currency: Currency
    initial_amount: float
    cash_balance: float
    holding_cost: float
    current_total: float
    total_pl: float
    current_year_pl: float
    current_year_pl_ratio: float | None
    previous_year_pl: float
    previous_year_pl_ratio: float | None


class AggregatedFundSnapshot(BaseModel):
    currency: Currency
    group_count: int
    initial_amount: float
    cash_balance: float
    holding_cost: float
    current_total: float
    total_pl: float
    current_year_pl: float
    current_year_pl_ratio: float | None
    previous_year_pl: float
    previous_year_pl_ratio: float | None


class FundSnapshots(BaseModel):
    funds: list[FundSnapshot]
    aggregated: list[AggregatedFundSnapshot]


class TaxSettlementRequest(BaseModel):
    transaction_id: str
    funding_group: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0.0)
    currency: Currency = Currency.JPY
    exchange_rate: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="JPY per USD when paying USD taxes",
    )

    @model_validator(mode="after")
    def validate_currency(self) -> "TaxSettlementRequest":
        if self.currency == Currency.USD:
            if self.exchange_rate is None:
                raise ValueError("exchange_rate is required when currency is USD")
        else:
            self.exchange_rate = None
        return self


class TaxSettlementRecord(BaseModel):
    id: str
    transaction_id: str
    funding_group: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0.0)
    currency: Currency
    exchange_rate: Optional[float] = Field(default=None, gt=0.0)
    jpy_equivalent: Optional[float] = Field(default=None, ge=0.0)
    recorded_at: date

    @model_validator(mode="after")
    def normalize_record(self) -> "TaxSettlementRecord":
        if self.currency == Currency.USD:
            if self.exchange_rate is None:
                raise ValueError("exchange_rate is required for USD settlements")
            jpy_equivalent = self.amount * self.exchange_rate
        else:
            jpy_equivalent = self.amount
            self.exchange_rate = None
        self.jpy_equivalent = round(jpy_equivalent, 2)
        return self


class TaxSettlementUpdate(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0.0)
    funding_group: Optional[str] = Field(default=None, min_length=1)
    exchange_rate: Optional[float] = Field(default=None, gt=0.0)


class HealthResponse(BaseModel):
    status: str
