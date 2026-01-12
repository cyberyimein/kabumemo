from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import isclose
from typing import Iterable
from uuid import uuid4

from ..models.schemas import (
    AggregatedFundSnapshot,
    Currency,
    FundSnapshot,
    FundSnapshots,
    FundingCapitalAdjustment,
    FundingGroup,
    Market,
    Position,
    PositionBreakdown,
    PositionGroupBreakdown,
    RoundTripYieldResponse,
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
    capital_adjustments: Iterable[FundingCapitalAdjustment] | None = None,
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
    adjustments = list(capital_adjustments or [])
    adjustments_by_group: dict[str, list[FundingCapitalAdjustment]] = defaultdict(list)
    for adjustment in adjustments:
        adjustments_by_group[adjustment.funding_group].append(adjustment)
    for entries in adjustments_by_group.values():
        entries.sort(key=lambda item: (item.effective_date, item.id))

    today = date.today()
    last_year_end = date(today.year - 1, 12, 31)
    prev_year_end = date(today.year - 2, 12, 31)

    def calculate_state(until: date | None) -> dict[str, dict[str, float]]:
        cash_flows: defaultdict[str, float] = defaultdict(float)
        inventories: dict[str, dict[str, dict[str, float]]] = {}
        cutoff = until or today

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
            contributions = sum(
                adjustment.amount
                for adjustment in adjustments_by_group.get(name, [])
                if adjustment.effective_date <= cutoff
            )
            base_amount = group.initial_amount + contributions
            cash_balance = base_amount + delta
            holdings = inventories.get(name, {})
            holding_cost = sum(record["total_cost"] for record in holdings.values())
            current_total = cash_balance + holding_cost
            state[name] = {
                "cash_balance": cash_balance,
                "holding_cost": holding_cost,
                "current_total": current_total,
                "contributions": contributions,
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

        # Remove net capital additions so realized profits are not inflated by fresh funding
        raw_current_year_pl = final_metrics["current_total"] - last_year_metrics["current_total"]
        current_year_contributions = (
            final_metrics["contributions"] - last_year_metrics["contributions"]
        )
        current_year_pl = raw_current_year_pl - current_year_contributions

        raw_previous_year_pl = last_year_metrics["current_total"] - prev_year_metrics["current_total"]
        previous_year_contributions = (
            last_year_metrics["contributions"] - prev_year_metrics["contributions"]
        )
        previous_year_pl = raw_previous_year_pl - previous_year_contributions
        current_year_ratio = safe_ratio(current_year_pl, last_year_metrics["current_total"])
        previous_year_ratio = safe_ratio(previous_year_pl, prev_year_metrics["current_total"])

        total_pl = final_metrics["current_total"] - (
            group.initial_amount + final_metrics["contributions"]
        )
        display_initial = group.initial_amount + final_metrics["contributions"]

        snapshots.append(
            FundSnapshot(
                name=name,
                currency=group.currency,
                initial_amount=round(display_initial, 2),
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


def compute_round_trip_yield(
    transactions: Iterable[Transaction],
    settlements: Iterable[TaxSettlementRecord],
) -> RoundTripYieldResponse:
    selected = sorted(
        list(transactions),
        key=lambda tx: (tx.trade_date, tx.id),
    )
    if not selected:
        raise ValueError("No transactions selected for yield calculation")

    symbol = selected[0].symbol
    funding_group = selected[0].funding_group
    market = selected[0].market
    currency = selected[0].cash_currency

    for tx in selected:
        if tx.symbol != symbol:
            raise ValueError("Selected transactions must share the same symbol")
        if tx.funding_group != funding_group:
            raise ValueError("Selected transactions must use the same funding group")
        if tx.market != market:
            raise ValueError("Selected transactions must belong to the same market")
        if tx.cash_currency != currency:
            raise ValueError("Selected transactions must share the same currency")

    total_quantity = sum(tx.quantity for tx in selected)
    if not isclose(total_quantity, 0.0, abs_tol=1e-6):
        raise ValueError("Selected transactions do not net to zero quantity")

    buys = [tx for tx in selected if tx.quantity > 0]
    sells = [tx for tx in selected if tx.quantity < 0]
    if not buys or not sells:
        raise ValueError("A valid round trip requires at least one buy and one sell")

    total_buy_quantity = sum(tx.quantity for tx in buys)
    total_sell_quantity = sum(-tx.quantity for tx in sells)
    total_buy_amount = sum(tx.gross_amount for tx in buys)
    total_sell_amount = sum(tx.gross_amount for tx in sells)

    if total_buy_amount <= 0:
        raise ValueError("Total buy amount must be greater than zero")

    gross_profit = total_sell_amount - total_buy_amount

    settlements_by_tx: dict[str, float] = defaultdict(float)
    for record in settlements:
        settlements_by_tx[record.transaction_id] += record.amount

    tax_total = sum(settlements_by_tx.get(tx.id, 0.0) for tx in selected)
    net_profit = gross_profit - tax_total

    return_ratio = gross_profit / total_buy_amount
    return_after_tax = net_profit / total_buy_amount

    start_date = min(tx.trade_date for tx in selected)
    end_date = max(tx.trade_date for tx in selected)
    raw_holding_days = (end_date - start_date).days
    effective_holding_days = max(raw_holding_days, 1)

    def annualize(ratio: float) -> float | None:
        base = 1.0 + ratio
        if base <= 0:
            return None
        exponent = 365 / effective_holding_days
        return pow(base, exponent) - 1

    annualized_return = annualize(return_ratio)
    annualized_return_after_tax = annualize(return_after_tax)

    def normalize_ratio(value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 6)

    return RoundTripYieldResponse(
        symbol=symbol,
        funding_group=funding_group,
        market=market,
        cash_currency=currency,
        transaction_ids=[tx.id for tx in selected],
        trade_count=len(selected),
        total_buy_quantity=round(total_buy_quantity, 6),
        total_sell_quantity=round(total_sell_quantity, 6),
        total_buy_amount=round(total_buy_amount, 2),
        total_sell_amount=round(total_sell_amount, 2),
        gross_profit=round(gross_profit, 2),
        tax_total=round(tax_total, 2),
        net_profit=round(net_profit, 2),
        return_ratio=normalize_ratio(return_ratio),
        return_after_tax=normalize_ratio(return_after_tax),
        annualized_return=normalize_ratio(annualized_return),
        annualized_return_after_tax=normalize_ratio(annualized_return_after_tax),
        holding_days=raw_holding_days,
        trade_window_start=start_date,
        trade_window_end=end_date,
    )
