from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable
from uuid import uuid4

from ..models.schemas import (
    AggregatedFundSnapshot,
    Currency,
    FundSnapshot,
    FundSnapshots,
    FundingGroup,
    Market,
    Position,
    PositionBreakdown,
    PositionGroupBreakdown,
    TaxSettlementRecord,
    TaxSettlementRequest,
    TaxSettlementUpdate,
    TaxStatus,
    Transaction,
)
from ..storage.repository import LocalDataRepository


def compute_positions(transactions: Iterable[Transaction]) -> list[Position]:
    inventory: dict[str, dict[Currency, defaultdict[str, dict[str, float]]]] = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(lambda: {"quantity": 0.0, "total_cost": 0.0})
        )
    )
    markets: dict[str, Market] = {}
    realized_totals: dict[str, defaultdict[Currency, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    realized_by_group: dict[
        str, defaultdict[Currency, defaultdict[str, float]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    sorted_transactions = [
        tx
        for _, tx in sorted(
            enumerate(transactions),
            key=lambda pair: (pair[1].trade_date, pair[0]),
        )
    ]

    for tx in sorted_transactions:
        symbol = tx.symbol
        currency = tx.cash_currency
        markets[symbol] = tx.market

        currency_groups = inventory[symbol][currency]
        group_record = currency_groups[tx.funding_group]

        total_realized = realized_totals[symbol]
        group_realized = realized_by_group[symbol][currency]

        if tx.quantity > 0:
            group_record["quantity"] += tx.quantity
            group_record["total_cost"] += tx.gross_amount
        else:
            if group_record["quantity"] <= 0:
                # No inventory recorded for this funding group; skip to avoid invalid math
                continue

            sell_qty = min(-tx.quantity, group_record["quantity"])
            avg_cost = (
                group_record["total_cost"] / group_record["quantity"]
                if group_record["quantity"]
                else 0.0
            )
            realized_profit = tx.gross_amount - avg_cost * sell_qty

            group_record["quantity"] += tx.quantity
            group_record["total_cost"] += avg_cost * tx.quantity

            if group_record["quantity"] <= 1e-9:
                group_record["quantity"] = 0.0
                group_record["total_cost"] = 0.0
            else:
                group_record["total_cost"] = max(group_record["total_cost"], 0.0)

            total_realized[currency] += realized_profit
            group_realized[tx.funding_group] += realized_profit

    positions: list[Position] = []
    for symbol, currency_groups in inventory.items():
        breakdown: list[PositionBreakdown] = []
        group_breakdown: list[PositionGroupBreakdown] = []
        total_realized_map = realized_totals[symbol]
        group_realized_map = realized_by_group[symbol]

        for currency, groups in currency_groups.items():
            total_qty = sum(record["quantity"] for record in groups.values())
            total_cost = sum(record["total_cost"] for record in groups.values())
            avg_cost = total_cost / total_qty if total_qty else 0.0

            breakdown.append(
                PositionBreakdown(
                    currency=currency,
                    quantity=round(total_qty, 4),
                    average_cost=round(avg_cost, 4),
                    realized_pl=round(total_realized_map[currency], 2),
                )
            )

            for funding_group, record in groups.items():
                qty = record["quantity"]
                realized_value = group_realized_map[currency][funding_group]
                avg_cost_group = record["total_cost"] / qty if qty else 0.0

                if abs(qty) <= 1e-9 and abs(realized_value) <= 1e-2:
                    continue

                group_breakdown.append(
                    PositionGroupBreakdown(
                        funding_group=funding_group,
                        currency=currency,
                        quantity=round(qty, 4),
                        average_cost=round(avg_cost_group, 4),
                        realized_pl=round(realized_value, 2),
                    )
                )

        breakdown.sort(key=lambda item: item.currency.value)
        group_breakdown.sort(key=lambda item: (item.currency.value, item.funding_group.lower()))

        positions.append(
            Position(
                symbol=symbol,
                market=markets[symbol],
                breakdown=breakdown,
                group_breakdown=group_breakdown,
            )
        )
    return positions

def compute_fund_snapshots(
    transactions: Iterable[Transaction],
    funding_groups: Iterable[FundingGroup],
    tax_settlements: Iterable[TaxSettlementRecord] | None = None,
) -> FundSnapshots:
    group_lookup = {group.name: group for group in funding_groups}
    sorted_transactions = [
        tx
        for _, tx in sorted(
            enumerate(transactions),
            key=lambda pair: (pair[1].trade_date, pair[0]),
        )
    ]
    settlements = list(tax_settlements or [])

    today = date.today()
    last_year_end = date(today.year - 1, 12, 31)
    prev_year_end = date(today.year - 2, 12, 31)

    def calculate_state(until: date | None) -> dict[str, dict[str, float]]:
        cash_flows: defaultdict[str, float] = defaultdict(float)
        inventories: dict[str, dict[str, dict[str, float]]] = {}

        for tx in sorted_transactions:
            if until and tx.trade_date > until:
                continue
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

        if settlements:
            for entry in settlements:
                if until and entry.recorded_at > until:
                    continue
                cash_flows[entry.funding_group] -= entry.amount

        state: dict[str, dict[str, float]] = {}
        for name, group in group_lookup.items():
            delta = cash_flows.get(name, 0.0)
            cash_balance = group.initial_amount + delta
            holdings = inventories.get(name, {})
            holding_cost = sum(record["total_cost"] for record in holdings.values())
            current_total = cash_balance + holding_cost
            state[name] = {
                "cash_balance": cash_balance,
                "holding_cost": holding_cost,
                "current_total": current_total,
            }
        return state

    final_state = calculate_state(None)
    last_year_state = calculate_state(last_year_end)
    prev_year_state = calculate_state(prev_year_end)

    def safe_ratio(numerator: float, denominator: float) -> float | None:
        return round(numerator / denominator, 6) if abs(denominator) > 1e-9 else None

    snapshots: list[FundSnapshot] = []
    for name, group in group_lookup.items():
        final_metrics = final_state[name]
        last_year_metrics = last_year_state[name]
        prev_year_metrics = prev_year_state[name]

        current_year_pl = final_metrics["current_total"] - last_year_metrics["current_total"]
        previous_year_pl = last_year_metrics["current_total"] - prev_year_metrics["current_total"]
        current_year_ratio = safe_ratio(current_year_pl, last_year_metrics["current_total"])
        previous_year_ratio = safe_ratio(previous_year_pl, prev_year_metrics["current_total"])

        total_pl = final_metrics["current_total"] - group.initial_amount

        snapshots.append(
            FundSnapshot(
                name=name,
                currency=group.currency,
                initial_amount=round(group.initial_amount, 2),
                cash_balance=round(final_metrics["cash_balance"], 2),
                holding_cost=round(final_metrics["holding_cost"], 2),
                current_total=round(final_metrics["current_total"], 2),
                total_pl=round(total_pl, 2),
                current_year_pl=round(current_year_pl, 2),
                current_year_pl_ratio=current_year_ratio,
                previous_year_pl=round(previous_year_pl, 2),
                previous_year_pl_ratio=previous_year_ratio,
            )
        )

    # Aggregate snapshots by currency
    aggregates: dict[Currency, dict[str, float]] = {
        currency: {
            "initial_amount": 0.0,
            "cash_balance": 0.0,
            "holding_cost": 0.0,
            "current_total": 0.0,
            "total_pl": 0.0,
            "current_year_pl": 0.0,
            "previous_year_pl": 0.0,
            "baseline_current": 0.0,
            "baseline_previous": 0.0,
        }
        for currency in Currency
    }
    group_counts: dict[Currency, int] = {currency: 0 for currency in Currency}

    for snapshot in snapshots:
        bucket = aggregates[snapshot.currency]
        group_counts[snapshot.currency] += 1
        bucket["initial_amount"] += snapshot.initial_amount
        bucket["cash_balance"] += snapshot.cash_balance
        bucket["holding_cost"] += snapshot.holding_cost
        bucket["current_total"] += snapshot.current_total
        bucket["total_pl"] += snapshot.total_pl
        bucket["current_year_pl"] += snapshot.current_year_pl
        bucket["previous_year_pl"] += snapshot.previous_year_pl
        bucket["baseline_current"] += last_year_state[snapshot.name]["current_total"]
        bucket["baseline_previous"] += prev_year_state[snapshot.name]["current_total"]

    aggregated_snapshots: list[AggregatedFundSnapshot] = []
    for currency, bucket in aggregates.items():
        if group_counts[currency] == 0:
            continue
        current_ratio = safe_ratio(bucket["current_year_pl"], bucket["baseline_current"])
        previous_ratio = safe_ratio(bucket["previous_year_pl"], bucket["baseline_previous"])
        aggregated_snapshots.append(
            AggregatedFundSnapshot(
                currency=currency,
                group_count=group_counts[currency],
                initial_amount=round(bucket["initial_amount"], 2),
                cash_balance=round(bucket["cash_balance"], 2),
                holding_cost=round(bucket["holding_cost"], 2),
                current_total=round(bucket["current_total"], 2),
                total_pl=round(bucket["total_pl"], 2),
                current_year_pl=round(bucket["current_year_pl"], 2),
                current_year_pl_ratio=current_ratio,
                previous_year_pl=round(bucket["previous_year_pl"], 2),
                previous_year_pl_ratio=previous_ratio,
            )
        )

    return FundSnapshots(funds=snapshots, aggregated=aggregated_snapshots)


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
