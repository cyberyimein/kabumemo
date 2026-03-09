from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Response, status

from ..models.schemas import (
    AnnualTaxSettlement,
    AnnualTaxSettlementCreate,
    AnnualTaxSettlementUpdate,
    BrokerImportApplyRequest,
    BrokerImportPreviewRequest,
    BrokerImportPreviewResponse,
    Currency,
    FundSnapshots,
    FundingCapitalAdjustment,
    FundingCapitalAdjustmentBase,
    FundingCapitalAdjustmentCreate,
    FundingGroup,
    FundingGroupUpdate,
    FxExchangeCreate,
    FxExchangeRecord,
    Market,
    QuoteSnapshot,
    HealthResponse,
    Position,
    PositionHistoryResponse,
    RealizedPnLRecord,
    RoundTripYieldRequest,
    RoundTripYieldResponse,
    StockSplitBase,
    StockSplitCreate,
    StockSplitRecord,
    TaxSettlementRecord,
    TaxSettlementRequest,
    TaxSettlementUpdate,
    TaxStatus,
    Transaction,
    TransactionCreate,
    TransactionUpdate,
)
from ..services.analytics import (
    _position_currency_for_transaction as analytics_position_currency_for_transaction,
    compute_fund_snapshots,
    compute_positions,
    compute_round_trip_yield,
    delete_tax_settlement,
    record_tax_settlement,
    update_tax_settlement,
)
from ..services.history import get_position_history
from ..services.broker_import import apply_broker_import, preview_broker_import, preview_items_to_transactions
from ..services.realized_pnl import rebuild_and_persist_realized_pnl
from ..services.stock_splits import adjusted_quantity_for_date
from ..storage.repository import LocalDataRepository
from ..services.quotes import refresh_quotes_if_needed

router = APIRouter(prefix="/api", tags=["kabucount"])
repository = LocalDataRepository()
repository.ensure_default_groups()


def _position_currency_for_trade(payload: Transaction | TransactionCreate | TransactionUpdate) -> Currency:
    market_currency = Currency.USD if payload.market == Market.US else Currency.JPY
    if (
        not payload.cross_currency
        and payload.trade_amount == payload.gross_amount
        and payload.settlement_currency == payload.cash_currency
        and payload.cash_currency != market_currency
    ):
        return payload.cash_currency
    return payload.trade_currency or (
        payload.buy_currency if payload.cross_currency and payload.buy_currency else payload.cash_currency
    )


def _available_sell_quantity(
    transactions: list[Transaction],
    stock_splits: list[StockSplitRecord],
    payload: Transaction | TransactionCreate | TransactionUpdate,
) -> float:
    target_currency = _position_currency_for_trade(payload)
    return sum(
        adjusted_quantity_for_date(tx, stock_splits, payload.trade_date)
        for tx in transactions
        if tx.symbol == payload.symbol
        and tx.market == payload.market
        and analytics_position_currency_for_transaction(tx) == target_currency
        and tx.broker_account_type == payload.broker_account_type
    )


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/transactions", response_model=list[Transaction])
def list_transactions() -> list[Transaction]:
    return repository.list_transactions()


@router.post(
    "/transactions",
    response_model=Transaction,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(payload: TransactionCreate) -> Transaction:
    transactions = repository.list_transactions()
    groups = repository.list_funding_groups()
    if payload.funding_group not in {group.name for group in groups}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Funding group not found",
        )
    if payload.quantity < 0:
        stock_splits = repository.list_stock_splits()
        available_quantity = _available_sell_quantity(transactions, stock_splits, payload)
        if available_quantity + payload.quantity < -1e-9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient position to complete sell order",
            )
    transaction = repository.add_transaction(payload)
    rebuild_and_persist_realized_pnl(repository)
    return transaction


@router.post(
    "/transactions/round-yield",
    response_model=RoundTripYieldResponse,
)
def calculate_round_trip_yield(payload: RoundTripYieldRequest) -> RoundTripYieldResponse:
    transactions = repository.list_transactions()
    transaction_lookup = {tx.id: tx for tx in transactions}
    missing = [tx_id for tx_id in payload.transaction_ids if tx_id not in transaction_lookup]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {missing[0]} not found",
        )

    selected_transactions = [transaction_lookup[tx_id] for tx_id in payload.transaction_ids]
    settlements = repository.list_tax_settlements()
    relevant_settlements = [
        record for record in settlements if record.transaction_id in payload.transaction_ids
    ]

    try:
        return compute_round_trip_yield(selected_transactions, relevant_settlements)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.api_route(
    "/transactions/{transaction_id}",
    methods=["PUT", "PATCH"],
    response_model=Transaction,
)
def update_transaction(transaction_id: str, payload: TransactionUpdate) -> Transaction:
    try:
        repository.get_transaction(transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    groups = repository.list_funding_groups()
    if payload.funding_group not in {group.name for group in groups}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Funding group not found",
        )

    transactions = repository.list_transactions()
    filtered_transactions = [tx for tx in transactions if tx.id != transaction_id]
    if payload.quantity < 0:
        stock_splits = repository.list_stock_splits()
        available_quantity = _available_sell_quantity(filtered_transactions, stock_splits, payload)
        if available_quantity + payload.quantity < -1e-9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient position to complete sell order",
            )

    if payload.taxed == TaxStatus.NO:
        settlements = repository.list_tax_settlements()
        if any(item.transaction_id == transaction_id for item in settlements):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot mark transaction as untaxed while a tax settlement exists",
            )

    updated_transaction = Transaction(id=transaction_id, **payload.model_dump())
    try:
        transaction = repository.update_transaction(updated_transaction)
        rebuild_and_persist_realized_pnl(repository)
        return transaction
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: str) -> Response:
    try:
        repository.delete_transaction(transaction_id)
        rebuild_and_persist_realized_pnl(repository)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/realized-pnl", response_model=list[RealizedPnLRecord])
def list_realized_pnl() -> list[RealizedPnLRecord]:
    return repository.list_realized_pnl_records()


@router.get("/positions", response_model=list[Position])
def get_positions() -> list[Position]:
    transactions = repository.list_transactions()
    fx_exchanges = repository.list_fx_exchanges()
    quotes = repository.list_quotes()
    realized_pnl_records = repository.list_realized_pnl_records()
    stock_splits = repository.list_stock_splits()
    try:
        return compute_positions(transactions, fx_exchanges, quotes, realized_pnl_records, stock_splits)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/positions/history", response_model=PositionHistoryResponse)
def get_positions_history(
    symbol: str,
    market: Market,
    period: str = "1y",
) -> PositionHistoryResponse:
    normalized_period = period.strip().lower() if period else "1y"
    if normalized_period not in {"1y", "1yr", "1year"}:
        normalized_period = "1y"
    transactions = repository.list_transactions()
    fx_exchanges = repository.list_fx_exchanges()
    return get_position_history(
        transactions=transactions,
        fx_exchanges=fx_exchanges,
        symbol=symbol,
        market=market,
        period=normalized_period,
    )


@router.get("/funds", response_model=FundSnapshots)
def get_funds() -> FundSnapshots:
    transactions = repository.list_transactions()
    groups = repository.list_funding_groups()
    settlements = repository.list_tax_settlements()
    annual_settlements = repository.list_annual_tax_settlements()
    adjustments = repository.list_capital_adjustments()
    fx_exchanges = repository.list_fx_exchanges()
    stock_splits = repository.list_stock_splits()
    realized_pnl_records = repository.list_realized_pnl_records()
    try:
        return compute_fund_snapshots(
            transactions,
            groups,
            settlements,
            annual_settlements,
            adjustments,
            fx_exchanges,
            stock_splits,
            realized_pnl_records,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/funding-groups", response_model=list[FundingGroup])
def list_funding_groups() -> list[FundingGroup]:
    return repository.list_funding_groups()


@router.post(
    "/funding-groups",
    response_model=FundingGroup,
    status_code=status.HTTP_201_CREATED,
)
def create_funding_group(payload: FundingGroup) -> FundingGroup:
    return repository.upsert_funding_group(payload)


@router.patch(
    "/funding-groups/{name}",
    response_model=FundingGroup,
)
def update_funding_group(name: str, payload: FundingGroupUpdate) -> FundingGroup:
    try:
        return repository.patch_funding_group(name, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/funding-groups/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_funding_group(name: str) -> Response:
    try:
        repository.delete_funding_group(name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/funding-groups/{name}/capital",
    response_model=FundingCapitalAdjustment,
    status_code=status.HTTP_201_CREATED,
)
def add_funding_capital(
    name: str, payload: FundingCapitalAdjustmentBase
) -> FundingCapitalAdjustment:
    try:
        repository.get_funding_group(name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    create_payload = FundingCapitalAdjustmentCreate(
        funding_group=name,
        amount=payload.amount,
        effective_date=payload.effective_date,
        notes=payload.notes,
    )
    return repository.add_capital_adjustment(create_payload)


@router.get(
    "/funding-groups/capital",
    response_model=list[FundingCapitalAdjustment],
)
def list_capital_adjustments() -> list[FundingCapitalAdjustment]:
    return repository.list_capital_adjustments()


@router.get("/stock-splits", response_model=list[StockSplitRecord])
def list_stock_splits() -> list[StockSplitRecord]:
    return repository.list_stock_splits()


@router.post(
    "/stock-splits",
    response_model=StockSplitRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_stock_split(payload: StockSplitBase) -> StockSplitRecord:
    record = repository.add_stock_split(StockSplitCreate(**payload.model_dump()))
    rebuild_and_persist_realized_pnl(repository)
    return record


@router.delete("/stock-splits/{split_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock_split(split_id: str) -> Response:
    try:
        repository.delete_stock_split(split_id)
        rebuild_and_persist_realized_pnl(repository)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/fx-exchanges", response_model=list[FxExchangeRecord])
def list_fx_exchanges() -> list[FxExchangeRecord]:
    return repository.list_fx_exchanges()


@router.post(
    "/fx-exchanges",
    response_model=FxExchangeRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_fx_exchange(payload: FxExchangeCreate) -> FxExchangeRecord:
    return repository.add_fx_exchange(payload)


@router.delete(
    "/fx-exchanges/{exchange_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_fx_exchange(exchange_id: str) -> Response:
    try:
        repository.delete_fx_exchange(exchange_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/quotes", response_model=QuoteSnapshot)
def list_quotes() -> QuoteSnapshot:
    records = repository.list_quotes()
    as_of = records[0].as_of if records else date.today()
    return QuoteSnapshot(as_of=as_of, records=records)


@router.post("/quotes/refresh", response_model=QuoteSnapshot)
def refresh_quotes(force: bool = False) -> QuoteSnapshot:
    snapshot = refresh_quotes_if_needed(repository, force=force)
    return snapshot


@router.get("/tax/settlements", response_model=list[TaxSettlementRecord])
def list_tax_settlements() -> list[TaxSettlementRecord]:
    return repository.list_tax_settlements()


@router.post(
    "/tax/settlements",
    response_model=TaxSettlementRecord,
    status_code=status.HTTP_201_CREATED,
)
def settle_tax(payload: TaxSettlementRequest) -> TaxSettlementRecord:
    try:
        return record_tax_settlement(repository, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch(
    "/tax/settlements/{settlement_id}",
    response_model=TaxSettlementRecord,
)
def edit_tax_settlement(settlement_id: str, payload: TaxSettlementUpdate) -> TaxSettlementRecord:
    try:
        return update_tax_settlement(repository, settlement_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/tax/settlements/{settlement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_tax_settlement(settlement_id: str) -> Response:
    try:
        delete_tax_settlement(repository, settlement_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tax/annual", response_model=list[AnnualTaxSettlement])
def list_annual_tax_settlements() -> list[AnnualTaxSettlement]:
    return repository.list_annual_tax_settlements()


@router.post(
    "/tax/annual",
    response_model=AnnualTaxSettlement,
    status_code=status.HTTP_201_CREATED,
)
def create_annual_tax_settlement(payload: AnnualTaxSettlementCreate) -> AnnualTaxSettlement:
    try:
        repository.get_funding_group(payload.funding_group)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return repository.add_annual_tax_settlement(payload)


@router.patch("/tax/annual/{settlement_id}", response_model=AnnualTaxSettlement)
def patch_annual_tax_settlement(
    settlement_id: str, payload: AnnualTaxSettlementUpdate
) -> AnnualTaxSettlement:
    try:
        return repository.update_annual_tax_settlement(settlement_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/tax/annual/{settlement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annual_tax_settlement(settlement_id: str) -> Response:
    try:
        repository.delete_annual_tax_settlement(settlement_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/imports/broker/preview", response_model=BrokerImportPreviewResponse)
def preview_broker_report_import(
    payload: BrokerImportPreviewRequest,
) -> BrokerImportPreviewResponse:
    return preview_broker_import(payload)


@router.post("/imports/broker/apply", response_model=BrokerImportPreviewResponse)
def apply_broker_report_import(
    payload: BrokerImportApplyRequest,
) -> BrokerImportPreviewResponse:
    preview = apply_broker_import(payload)
    transactions = preview_items_to_transactions(preview.items)
    if payload.replace_existing_transactions:
        repository.replace_transactions(transactions)
        repository.clear_tax_settlements()
        rebuild_and_persist_realized_pnl(repository, transactions)
        preview.applied_count = len(transactions)
        preview.skipped_count = 0
        return preview

    merged_transactions, applied_count, skipped_count = repository.merge_transactions_skip_duplicates(transactions)
    if applied_count:
        rebuild_and_persist_realized_pnl(repository, merged_transactions)
    preview.applied_count = applied_count
    preview.skipped_count = skipped_count
    if skipped_count:
        preview.warnings.append(f"Skipped {skipped_count} duplicate transactions")
    return preview
