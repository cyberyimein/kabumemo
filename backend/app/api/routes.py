from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from ..models.schemas import (
    FundSnapshots,
    FundingGroup,
    FundingGroupUpdate,
    HealthResponse,
    Position,
    TaxSettlementRequest,
    TaxSettlementRecord,
    TaxSettlementUpdate,
    Transaction,
    TransactionCreate,
    TransactionUpdate,
    TaxStatus,
)
from ..services.analytics import (
    compute_fund_snapshots,
    compute_positions,
    delete_tax_settlement,
    record_tax_settlement,
    update_tax_settlement,
)
from ..storage.repository import LocalDataRepository

router = APIRouter(prefix="/api", tags=["kabucount"])
repository = LocalDataRepository()
repository.ensure_default_groups()


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
        available_quantity = sum(
            tx.quantity
            for tx in transactions
            if tx.symbol == payload.symbol
            and tx.market == payload.market
            and tx.cash_currency == payload.cash_currency
        )
        if available_quantity + payload.quantity < -1e-9:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient position to complete sell order",
            )
    return repository.add_transaction(payload)


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
        available_quantity = sum(
            tx.quantity
            for tx in filtered_transactions
            if tx.symbol == payload.symbol
            and tx.market == payload.market
            and tx.cash_currency == payload.cash_currency
        )
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
        return repository.update_transaction(updated_transaction)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: str) -> Response:
    try:
        repository.delete_transaction(transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/positions", response_model=list[Position])
def get_positions() -> list[Position]:
    transactions = repository.list_transactions()
    return compute_positions(transactions)


@router.get("/funds", response_model=FundSnapshots)
def get_funds() -> FundSnapshots:
    transactions = repository.list_transactions()
    groups = repository.list_funding_groups()
    settlements = repository.list_tax_settlements()
    return compute_fund_snapshots(transactions, groups, settlements)


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
