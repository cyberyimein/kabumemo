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


class BrokerAccountType(str, Enum):
    NISA = "NISA"
    SPECIFIC = "SPECIFIC"
    GENERAL = "GENERAL"
    UNKNOWN = "UNKNOWN"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


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


class StockSplitBase(BaseModel):
    symbol: str = Field(..., min_length=1)
    market: Market
    effective_date: date
    ratio_before: float = Field(..., gt=0.0)
    ratio_after: float = Field(..., gt=0.0)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def normalize_symbol(self) -> "StockSplitBase":
        normalized = self.symbol.strip().upper()
        if self.market == Market.JP and normalized and not normalized.endswith(".T"):
            normalized = f"{normalized}.T"
        self.symbol = normalized
        return self


class StockSplitCreate(StockSplitBase):
    pass


class StockSplitRecord(StockSplitBase):
    id: str


class FxExchangeBase(BaseModel):
    exchange_date: date = Field(default_factory=date.today)
    from_currency: Currency
    to_currency: Currency
    from_amount: float = Field(..., gt=0.0)
    to_amount: Optional[float] = Field(default=None, gt=0.0)
    rate: Optional[float] = Field(default=None, gt=0.0, description="JPY per USD")
    notes: Optional[str] = None
    transaction_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_pair(self) -> "FxExchangeBase":
        if self.from_currency == self.to_currency:
            raise ValueError("from_currency and to_currency must differ")
        if self.to_amount is None and self.rate is None:
            raise ValueError("to_amount or rate is required")
        if self.to_amount is None:
            if self.from_currency == Currency.JPY and self.to_currency == Currency.USD:
                self.to_amount = self.from_amount / self.rate
            elif self.from_currency == Currency.USD and self.to_currency == Currency.JPY:
                self.to_amount = self.from_amount * self.rate
            else:
                self.to_amount = self.from_amount
        if self.rate is None:
            if self.from_currency == Currency.JPY and self.to_currency == Currency.USD:
                self.rate = self.from_amount / self.to_amount
            elif self.from_currency == Currency.USD and self.to_currency == Currency.JPY:
                self.rate = self.to_amount / self.from_amount
            else:
                self.rate = self.from_amount / self.to_amount
        return self


class FxExchangeCreate(FxExchangeBase):
    pass


class FxExchangeRecord(FxExchangeBase):
    id: str
    to_amount: float


class TransactionBase(BaseModel):
    trade_date: date = Field(default_factory=date.today)
    symbol: str = Field(..., min_length=1)
    quantity: float
    gross_amount: float = Field(..., gt=0.0, description="Total cash outlay or proceeds")
    funding_group: str = Field(..., min_length=1)
    cash_currency: Currency
    position_group: Optional[str] = None
    settlement_group: Optional[str] = None
    trade_currency: Optional[Currency] = None
    trade_amount: Optional[float] = Field(default=None, gt=0.0)
    settlement_currency: Optional[Currency] = None
    settlement_amount: Optional[float] = Field(default=None, gt=0.0)
    broker_account_type: BrokerAccountType = BrokerAccountType.UNKNOWN
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

        if self.position_group is None:
            self.position_group = self.funding_group
        if self.settlement_group is None:
            self.settlement_group = self.funding_group

        default_trade_currency = Currency.USD if self.market == Market.US else Currency.JPY
        if self.trade_currency is None:
            self.trade_currency = default_trade_currency
        if self.trade_amount is None:
            self.trade_amount = self.gross_amount
        if self.settlement_currency is None:
            self.settlement_currency = self.cash_currency
        if self.settlement_amount is None:
            self.settlement_amount = self.gross_amount

        if self.cross_currency:
            if self.quantity >= 0:
                raise ValueError("cross_currency is only valid for sell transactions")
            if self.buy_currency is None or self.sell_currency is None:
                raise ValueError("buy_currency and sell_currency are required")
            if self.buy_currency == self.sell_currency:
                raise ValueError("buy_currency and sell_currency must differ")
            if self.cash_currency != self.buy_currency:
                raise ValueError("cash_currency must match buy_currency")
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


class RealizedPnLAllocation(BaseModel):
    funding_group: str
    quantity: float
    cost_basis: float
    realized_pl: float


class RealizedPnLRecord(BaseModel):
    id: str
    sell_transaction_id: str
    trade_date: date
    symbol: str
    market: Market
    broker_account_type: BrokerAccountType
    position_currency: Currency
    settlement_currency: Currency
    quantity: float = Field(..., gt=0.0)
    matched_quantity: float = Field(default=0.0, ge=0.0)
    unmatched_quantity: float = Field(default=0.0, ge=0.0)
    proceeds_amount: float
    cost_basis: float
    realized_pl: float
    allocations: list[RealizedPnLAllocation] = Field(default_factory=list)
    memo: Optional[str] = None


class QuoteRecord(BaseModel):
    symbol: str
    market: Market
    price: float
    currency: Currency
    as_of: date


class QuoteSnapshot(BaseModel):
    as_of: date
    records: list[QuoteRecord]


class PriceHistoryPoint(BaseModel):
    date: date
    close: float


class TradeMarker(BaseModel):
    date: date
    price: float
    side: TradeSide
    quantity: float
    currency: Currency
    transaction_id: str


class PositionHistoryResponse(BaseModel):
    symbol: str
    market: Market
    currency: Currency
    series: list[PriceHistoryPoint]
    markers: list[TradeMarker]


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


class AnnualTaxSettlementBase(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    funding_group: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0.0)
    currency: Currency = Currency.JPY
    notes: Optional[str] = None


class AnnualTaxSettlementCreate(AnnualTaxSettlementBase):
    recorded_at: date = Field(default_factory=date.today)


class AnnualTaxSettlementUpdate(BaseModel):
    funding_group: Optional[str] = Field(default=None, min_length=1)
    amount: Optional[float] = Field(default=None, gt=0.0)
    currency: Optional[Currency] = None
    notes: Optional[str] = None
    recorded_at: Optional[date] = None


class AnnualTaxSettlement(AnnualTaxSettlementBase):
    id: str
    recorded_at: date


class BrokerImportFile(BaseModel):
    file_name: str
    content_base64: str
    encoding_hint: Optional[str] = None


class BrokerImportPreviewRequest(BaseModel):
    domestic_report: Optional[BrokerImportFile] = None
    us_report: Optional[BrokerImportFile] = None
    position_group_jpy: str = "JPY"
    settlement_group_jpy: str = "JPY"
    position_group_usd: str = "USD"
    settlement_group_usd: str = "USD"


class BrokerImportPreviewItem(BaseModel):
    trade_date: date
    symbol: str
    market: Market
    quantity: float
    trade_currency: Currency
    trade_amount: float
    settlement_currency: Currency
    settlement_amount: float
    broker_account_type: BrokerAccountType
    position_group: str
    settlement_group: str
    source_file: str
    source_line: int
    transaction_id: str
    taxed: TaxStatus
    memo: Optional[str] = None


class BrokerImportPreviewResponse(BaseModel):
    items: list[BrokerImportPreviewItem]
    warnings: list[str] = Field(default_factory=list)
    applied_count: int = 0
    skipped_count: int = 0


class BrokerImportApplyRequest(BrokerImportPreviewRequest):
    replace_existing_transactions: bool = False


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
