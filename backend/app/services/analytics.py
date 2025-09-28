from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable
from uuid import uuid4

from ..models.schemas import (
    Currency,
    FundSnapshot,
    FundingGroup,
    Market,
    Position,
    TaxSettlementRecord,
    TaxSettlementRequest,
    TaxSettlementUpdate,
    TaxStatus,
    Transaction,
)
from ..storage.repository import LocalDataRepository


def compute_positions(transactions: Iterable[Transaction]) -> list[Position]:
    inventory: dict[str, dict[str, float]] = {}
    markets: dict[str, Market] = {}
    realized: defaultdict[str, float] = defaultdict(float)
    sorted_transactions = [
        tx
        for _, tx in sorted(
            enumerate(transactions),
            key=lambda pair: (pair[1].trade_date, pair[0]),
        )
    ]

    for tx in sorted_transactions:
        record = inventory.setdefault(
            tx.symbol,
            {
                "quantity": 0.0,
                "total_cost": 0.0,
            },
        )
        markets[tx.symbol] = tx.market
        current_qty = record["quantity"]
        total_cost = record["total_cost"]

        if tx.quantity > 0:
            new_qty = current_qty + tx.quantity
            new_cost = total_cost + tx.gross_amount
        else:
            sell_qty = min(-tx.quantity, current_qty)
            avg_cost = total_cost / current_qty if current_qty else 0.0
            realized_profit = tx.gross_amount - avg_cost * sell_qty
            realized[tx.symbol] += realized_profit
            new_qty = current_qty + tx.quantity
            new_cost = total_cost + avg_cost * tx.quantity
            if new_qty <= 1e-9:
                new_qty = 0.0
                new_cost = 0.0
        record["quantity"] = new_qty
        record["total_cost"] = max(new_cost, 0.0)

    positions: list[Position] = []
    for symbol, record in inventory.items():
        qty = record["quantity"]
        total_cost = record["total_cost"]
        avg_cost = total_cost / qty if qty else 0.0
        positions.append(
            Position(
                symbol=symbol,
                quantity=round(qty, 4),
                average_cost=round(avg_cost, 4),
                realized_pl=round(realized[symbol], 2),
                market=markets[symbol],
            )
        )
    return positions


def compute_fund_snapshots(
    transactions: Iterable[Transaction],
    funding_groups: Iterable[FundingGroup],
    tax_settlements: Iterable[TaxSettlementRecord] | None = None,
) -> list[FundSnapshot]:
    group_lookup = {group.name: group for group in funding_groups}
    cash_flows: defaultdict[str, float] = defaultdict(float)
    inventories: dict[str, dict[str, dict[str, float]]] = {}

    sorted_transactions = [
        tx
        for _, tx in sorted(
            enumerate(transactions),
            key=lambda pair: (pair[1].trade_date, pair[0]),
        )
    ]

    for tx in sorted_transactions:
        amount = tx.gross_amount
        if tx.quantity > 0:
            cash_flows[tx.funding_group] -= amount
        else:
            cash_flows[tx.funding_group] += amount

        group_inventory = inventories.setdefault(tx.funding_group, {})
        record = group_inventory.setdefault(
            tx.symbol,
            {
                "quantity": 0.0,
                "total_cost": 0.0,
            },
        )
        current_qty = record["quantity"]
        total_cost = record["total_cost"]

        if tx.quantity > 0:
            record["quantity"] = current_qty + tx.quantity
            record["total_cost"] = total_cost + amount
        else:
            sell_qty = min(-tx.quantity, current_qty)
            if current_qty <= 0:
                continue
            avg_cost = total_cost / current_qty if current_qty else 0.0
            cost_reduction = avg_cost * sell_qty
            new_qty = current_qty + tx.quantity
            new_cost = total_cost - cost_reduction
            if new_qty <= 1e-9:
                new_qty = 0.0
                new_cost = 0.0
            record["quantity"] = new_qty
            record["total_cost"] = max(new_cost, 0.0)

    if tax_settlements:
        for entry in tax_settlements:
            cash_flows[entry.funding_group] -= entry.amount

    snapshots: list[FundSnapshot] = []
    for name, group in group_lookup.items():
        delta = cash_flows.get(name, 0.0)
        cash_balance = group.initial_amount + delta
        holdings = inventories.get(name, {})
        holding_cost = sum(record["total_cost"] for record in holdings.values())
        current_total = cash_balance + holding_cost
        total_pl = current_total - group.initial_amount
        snapshots.append(
            FundSnapshot(
                name=name,
                currency=group.currency,
                initial_amount=group.initial_amount,
                cash_balance=round(cash_balance, 2),
                holding_cost=round(holding_cost, 2),
                current_total=round(current_total, 2),
                total_pl=round(total_pl, 2),
            )
        )
    return snapshots


def record_tax_settlement(
    repo: LocalDataRepository,
    payload: TaxSettlementRequest,
) -> TaxSettlementRecord:
    transaction = repo.get_transaction(payload.transaction_id)
    if transaction.taxed == TaxStatus.YES:
        raise ValueError("Transaction already marked as taxed")
    if transaction.funding_group != payload.funding_group:
        raise ValueError("Funding group does not match transaction record")

    group = repo.get_funding_group(payload.funding_group)
    if group.currency != payload.currency:
        raise ValueError("Tax payment currency must match funding group currency")

    repo.mark_transaction_taxed(payload.transaction_id)
    record = TaxSettlementRecord(
        id=str(uuid4()),
        transaction_id=payload.transaction_id,
        amount=payload.amount,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        funding_group=payload.funding_group,
        jpy_equivalent=None,
        recorded_at=date.today(),
    )
    return repo.add_tax_settlement(record)


def update_tax_settlement(
    repo: LocalDataRepository,
    settlement_id: str,
    payload: TaxSettlementUpdate,
) -> TaxSettlementRecord:
    original = repo.get_tax_settlement(settlement_id)
    transaction = repo.get_transaction(original.transaction_id)

    funding_group = payload.funding_group or original.funding_group
    if transaction.funding_group != funding_group:
        raise ValueError("Funding group must match the transaction record")

    group = repo.get_funding_group(funding_group)
    if group.currency != original.currency:
        raise ValueError("Tax payment currency must match funding group currency")

    amount = payload.amount or original.amount
    exchange_rate = payload.exchange_rate
    if exchange_rate is None and original.exchange_rate is not None:
        exchange_rate = original.exchange_rate

    updated_record = TaxSettlementRecord(
        id=original.id,
        transaction_id=original.transaction_id,
        amount=amount,
        currency=original.currency,
        exchange_rate=exchange_rate,
        funding_group=funding_group,
        jpy_equivalent=None,
        recorded_at=original.recorded_at,
    )
    return repo.update_tax_settlement(settlement_id, updated_record)


def delete_tax_settlement(
    repo: LocalDataRepository,
    settlement_id: str,
) -> None:
    record = repo.get_tax_settlement(settlement_id)
    repo.delete_tax_settlement(settlement_id)
    repo.mark_transaction_untaxed(record.transaction_id)
