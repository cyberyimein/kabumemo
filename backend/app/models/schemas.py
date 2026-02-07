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


class FxExchangeBase(BaseModel):
    exchange_date: date = Field(default_factory=date.today)
    from_currency: Currency
    to_currency: Currency
    from_amount: float = Field(..., gt=0.0)
    rate: float = Field(..., gt=0.0, description="JPY per USD")
    notes: Optional[str] = None
    transaction_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_pair(self) -> "FxExchangeBase":
        if self.from_currency == self.to_currency:
            raise ValueError("from_currency and to_currency must differ")
        return self


class FxExchangeCreate(FxExchangeBase):
    pass


class FxExchangeRecord(FxExchangeBase):
    id: str
    to_amount: float

    @model_validator(mode="after")
    def compute_to_amount(self) -> "FxExchangeRecord":
        if self.from_currency == Currency.JPY and self.to_currency == Currency.USD:
            converted = self.from_amount / self.rate
        elif self.from_currency == Currency.USD and self.to_currency == Currency.JPY:
            converted = self.from_amount * self.rate
        else:
            converted = self.from_amount
        self.to_amount = round(converted, 6)
        return self


class TransactionBase(BaseModel):
    trade_date: date = Field(default_factory=date.today)
    symbol: str = Field(..., min_length=1)
    quantity: float
    gross_amount: float = Field(..., gt=0.0, description="Total cash outlay or proceeds")
    funding_group: str = Field(..., min_length=1)
    cash_currency: Currency
    cross_currency: bool = False
    buy_currency: Optional[Currency] = None
    sell_currency: Optional[Currency] = None
    market: Market
    taxed: TaxStatus = TaxStatus.YES
    memo: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_nonzero(cls, value: float) -> float:
        if value == 0:
            raise ValueError("quantity must not be zero")
        return value

    @model_validator(mode="after")
    def validate_cross_currency(self) -> "TransactionBase":
        if self.market == Market.JP:
            normalized = self.symbol.strip().upper()
            if normalized and not normalized.endswith(".T"):
                normalized = f"{normalized}.T"
            self.symbol = normalized
        if self.cross_currency:
            if self.quantity >= 0:
                raise ValueError("cross_currency is only valid for sell transactions")
            if self.buy_currency is None or self.sell_currency is None:
                raise ValueError("buy_currency and sell_currency are required")
            if self.buy_currency == self.sell_currency:
                raise ValueError("buy_currency and sell_currency must differ")
            if self.cash_currency != self.sell_currency:
                raise ValueError("cash_currency must match sell_currency")
        else:
            self.buy_currency = None
            self.sell_currency = None
        return self


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
    current_price: float | None = None
    unrealized_pl: float | None = None


class PositionGroupBreakdown(BaseModel):
    funding_group: str
    currency: Currency
    quantity: float
    average_cost: float
    realized_pl: float
    current_price: float | None = None
    unrealized_pl: float | None = None


class Position(BaseModel):
    symbol: str
    market: Market
    breakdown: list[PositionBreakdown]
    group_breakdown: list[PositionGroupBreakdown] = Field(default_factory=list)


class QuoteRecord(BaseModel):
    symbol: str
    market: Market
    price: float
    currency: Currency
    as_of: date


class QuoteSnapshot(BaseModel):
    as_of: date
    records: list[QuoteRecord]


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
        description="Legacy USD tax exchange rate",
    )
    balance_exchange_rate: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="JPY per USD for balance hint",
    )

    @model_validator(mode="after")
    def validate_currency(self) -> "TaxSettlementRequest":
        if self.currency != Currency.JPY:
            raise ValueError("Tax payments must be in JPY")
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
    balance_exchange_rate: Optional[float] = Field(default=None, gt=0.0)
    balance_usd_required: Optional[float] = Field(default=None, ge=0.0)
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
        if self.balance_exchange_rate:
            self.balance_usd_required = round(
                self.jpy_equivalent / self.balance_exchange_rate, 4
            )
        else:
            self.balance_usd_required = None
        return self


class TaxSettlementUpdate(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0.0)
    funding_group: Optional[str] = Field(default=None, min_length=1)
    exchange_rate: Optional[float] = Field(default=None, gt=0.0)
    balance_exchange_rate: Optional[float] = Field(default=None, gt=0.0)


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
