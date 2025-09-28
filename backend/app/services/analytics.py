from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from ..models.schemas import (
    Currency,
    FundSnapshot,
    FundingGroup,
    Position,
    TaxSettlementRequest,
    TaxSettlementResponse,
    TaxStatus,
    Transaction,
)
from ..storage.repository import LocalDataRepository


def compute_positions(transactions: Iterable[Transaction]) -> list[Position]:
    inventory: dict[str, dict[str, float]] = {}
    realized: defaultdict[str, float] = defaultdict(float)
    sorted_transactions = sorted(transactions, key=lambda t: (t.trade_date, t.id))

    for tx in sorted_transactions:
        record = inventory.setdefault(
            tx.symbol,
            {
                "quantity": 0.0,
                "total_cost": 0.0,
                "market": tx.market,
            },
        )
        current_qty = record["quantity"]
        total_cost = record["total_cost"]
        avg_cost = total_cost / current_qty if current_qty else 0.0

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
        record["market"] = tx.market

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
                market=record["market"],
            )
        )
    return positions


def compute_fund_snapshots(
    transactions: Iterable[Transaction],
    funding_groups: Iterable[FundingGroup],
    tax_settlements: Iterable[dict[str, object]] | None = None,
) -> list[FundSnapshot]:
    group_lookup = {group.name: group for group in funding_groups}
    cash_flows: defaultdict[str, float] = defaultdict(float)

    for tx in transactions:
        amount = tx.gross_amount
        if tx.quantity > 0:
            cash_flows[tx.funding_group] -= amount
        else:
            cash_flows[tx.funding_group] += amount

    if tax_settlements:
        for entry in tax_settlements:
            group = entry.get("funding_group")
            if not group:
                continue
            amount = float(entry.get("amount"))
            cash_flows[group] -= amount

    snapshots: list[FundSnapshot] = []
    for name, group in group_lookup.items():
        delta = cash_flows.get(name, 0.0)
        current_total = group.initial_amount + delta
        total_pl = delta
        snapshots.append(
            FundSnapshot(
                name=name,
                currency=group.currency,
                initial_amount=group.initial_amount,
                current_total=round(current_total, 2),
                total_pl=round(total_pl, 2),
            )
        )
    return snapshots


def record_tax_settlement(
    repo: LocalDataRepository,
    payload: TaxSettlementRequest,
) -> TaxSettlementResponse:
    transaction = repo.get_transaction(payload.transaction_id)
    if transaction.taxed == TaxStatus.YES:
        raise ValueError("Transaction already marked as taxed")
    if transaction.funding_group != payload.funding_group:
        raise ValueError("Funding group does not match transaction record")

    group = repo.get_funding_group(payload.funding_group)
    if group.currency != payload.currency:
        raise ValueError("Tax payment currency must match funding group currency")

    repo.mark_transaction_taxed(payload.transaction_id)
    settlement = {
        "transaction_id": payload.transaction_id,
        "amount": payload.amount,
        "currency": payload.currency.value,
        "exchange_rate": payload.exchange_rate,
        "funding_group": payload.funding_group,
        "recorded_at": date.today().isoformat(),
    }
    repo.add_tax_settlement(settlement)

    jpy_equivalent = payload.amount
    if payload.currency == Currency.USD:
        assert payload.exchange_rate is not None
        jpy_equivalent = payload.amount * payload.exchange_rate

    return TaxSettlementResponse(
        transaction_id=payload.transaction_id,
        amount_paid=payload.amount,
        currency=payload.currency,
        jpy_equivalent=round(jpy_equivalent, 2),
        new_tax_status=TaxStatus.YES,
    )
