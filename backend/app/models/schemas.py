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


class FundingCapitalAdjustmentBase(BaseModel):
    amount: float = Field(..., gt=0.0)
    effective_date: date
    notes: Optional[str] = None


class FundingCapitalAdjustmentCreate(FundingCapitalAdjustmentBase):
    funding_group: str = Field(..., min_length=1)


class FundingCapitalAdjustment(FundingCapitalAdjustmentBase):
    id: str
    funding_group: str


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


class PositionGroupBreakdown(BaseModel):
    funding_group: str
    currency: Currency
    quantity: float
    average_cost: float
    realized_pl: float


class Position(BaseModel):
    symbol: str
    market: Market
    breakdown: list[PositionBreakdown]
    group_breakdown: list[PositionGroupBreakdown] = Field(default_factory=list)


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


class RoundTripYieldRequest(BaseModel):
    transaction_ids: list[str] = Field(..., min_length=2)

    @field_validator("transaction_ids")
    @classmethod
    def ensure_unique_ids(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) < 2:
            raise ValueError("At least two transaction ids are required")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate transaction ids are not allowed")
        return normalized


class RoundTripYieldResponse(BaseModel):
    symbol: str
    funding_group: str
    market: Market
    cash_currency: Currency
    transaction_ids: list[str]
    trade_count: int
    total_buy_quantity: float
    total_sell_quantity: float
    total_buy_amount: float
    total_sell_amount: float
    gross_profit: float
    tax_total: float
    net_profit: float
    return_ratio: float | None
    return_after_tax: float | None
    annualized_return: float | None
    annualized_return_after_tax: float | None
    holding_days: int
    trade_window_start: date
    trade_window_end: date


class HealthResponse(BaseModel):
    status: str
