from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import isclose
from typing import Iterable
from uuid import uuid4

from ..models.schemas import (
    AggregatedFundSnapshot,
    AnnualTaxSettlement,
    CashActivity,
    CashActivityCategory,
    CashDirection,
    Currency,
    FxExchangeRecord,
    FundSnapshot,
    FundSnapshots,
    FundingCapitalAdjustment,
    FundingGroup,
    Market,
    QuoteRecord,
    Position,
    PositionBreakdown,
    PositionGroupBreakdown,
    RealizedPnLRecord,
    StockSplitRecord,
    RoundTripYieldResponse,
    TaxSettlementRecord,
    TaxSettlementRequest,
    TaxSettlementUpdate,
    TaxStatus,
    Transaction,
)
from .stock_splits import apply_splits_to_lots, build_split_schedule
from ..storage.repository import LocalDataRepository


def _market_currency(market: Market) -> Currency:
    return Currency.USD if market == Market.US else Currency.JPY


def _convert_with_rate(
    *,
    amount: float,
    from_currency: Currency,
    to_currency: Currency,
    rate: float,
) -> float:
    if from_currency == to_currency:
        return amount
    if from_currency == Currency.JPY and to_currency == Currency.USD:
        return amount / rate
    if from_currency == Currency.USD and to_currency == Currency.JPY:
        return amount * rate
    return amount


def _fx_lookup(exchanges: Iterable[FxExchangeRecord]) -> dict[str, FxExchangeRecord]:
    return {item.transaction_id: item for item in exchanges if item.transaction_id}


def _resolve_fx_group_name(
    group_lookup: dict[str, FundingGroup],
    currency: Currency,
) -> str:
    preferred_name = currency.value
    preferred_group = group_lookup.get(preferred_name)
    if preferred_group and preferred_group.currency == currency:
        return preferred_name

    matches = sorted(
        name for name, group in group_lookup.items() if group.currency == currency
    )
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"Funding group not found for FX currency {currency.value}")
    raise ValueError(
        f"Multiple funding groups found for FX currency {currency.value}; use the canonical group name"
    )


def _position_currency_for_transaction(tx: Transaction) -> Currency:
    # Legacy records may have been stored only in settlement currency even for US stocks.
    # Treat those as cash-currency positions unless an explicit trade amount/currency is present.
    if (
        not tx.cross_currency
        and tx.trade_amount == tx.gross_amount
        and tx.settlement_currency == tx.cash_currency
        and tx.cash_currency != _market_currency(tx.market)
    ):
        return tx.cash_currency
    return tx.trade_currency or (
        tx.buy_currency if tx.cross_currency and tx.buy_currency else tx.cash_currency
    )


def _position_account_key(tx: Transaction) -> tuple[str, Market, str]:
    return (tx.symbol, tx.market, tx.broker_account_type.value)


def _effective_position_amount(
    tx: Transaction,
    fx_map: dict[str, FxExchangeRecord],
    position_currency: Currency,
) -> float:
    effective_amount = tx.trade_amount or tx.gross_amount
    if tx.cross_currency and tx.cash_currency != position_currency:
        fx_record = fx_map.get(tx.id)
        if not fx_record:
            raise ValueError(f"FX exchange required for transaction {tx.id} ({tx.symbol})")
        if {fx_record.from_currency, fx_record.to_currency} != {tx.cash_currency, position_currency}:
            raise ValueError(f"FX exchange currency mismatch for transaction {tx.id}")
        effective_amount = _convert_with_rate(
            amount=tx.gross_amount,
            from_currency=tx.cash_currency,
            to_currency=position_currency,
            rate=fx_record.rate,
        )
    return effective_amount


def compute_positions(
    transactions: Iterable[Transaction],
    fx_exchanges: Iterable[FxExchangeRecord] | None = None,
    quotes: Iterable[QuoteRecord] | None = None,
    realized_pnl_records: Iterable[RealizedPnLRecord] | None = None,
    stock_splits: Iterable[StockSplitRecord] | None = None,
) -> list[Position]:
    fx_map = _fx_lookup(fx_exchanges or [])
    split_schedule = build_split_schedule(stock_splits or [])
    quote_map: dict[tuple[str, Market], QuoteRecord] = {
        (quote.symbol, quote.market): quote for quote in (quotes or [])
    }

    lot_inventory: dict[
        tuple[str, Market, str], dict[Currency, list[dict[str, float | str]]]
    ] = defaultdict(
        lambda: defaultdict(list)
    )
    applied_split_counts: dict[tuple[str, Market, str, Currency], int] = defaultdict(int)
    realized_totals: dict[
        tuple[str, Market, str], defaultdict[Currency, float]
    ] = defaultdict(
        lambda: defaultdict(float)
    )
    realized_by_group: dict[
        tuple[str, Market, str], defaultdict[Currency, defaultdict[str, float]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    sorted_transactions = [
        tx
        for _, tx in sorted(
            enumerate(transactions),
            key=lambda pair: (pair[1].trade_date, pair[0]),
        )
    ]

    for tx in sorted_transactions:
        position_key = _position_account_key(tx)
        position_currency = _position_currency_for_transaction(tx)
        lots = lot_inventory[position_key][position_currency]
        split_key = (
            tx.symbol,
            tx.market.value,
        )
        applied_key = (tx.symbol, tx.market, tx.broker_account_type.value, position_currency)
        applied_split_counts[applied_key] = apply_splits_to_lots(
            lots,
            split_schedule.get(split_key, []),
            applied_split_counts[applied_key],
            tx.trade_date,
        )
        total_realized = realized_totals[position_key]
        group_realized = realized_by_group[position_key][position_currency]
        effective_amount = _effective_position_amount(tx, fx_map, position_currency)
        position_group = tx.position_group or tx.funding_group

        if tx.quantity > 0:
            unit_cost = effective_amount / tx.quantity if tx.quantity else 0.0
            lots.append(
                {
                    "group": position_group,
                    "quantity": tx.quantity,
                    "unit_cost": unit_cost,
                }
            )
        else:
            sell_quantity = -tx.quantity
            if sell_quantity <= 0:
                continue
            remaining_quantity = sell_quantity
            proceeds_per_share = effective_amount / sell_quantity if sell_quantity else 0.0

            for lot in lots:
                lot_quantity = float(lot["quantity"])
                if lot_quantity <= 1e-9 or remaining_quantity <= 1e-9:
                    continue

                consumed_quantity = min(remaining_quantity, lot_quantity)
                lot_unit_cost = float(lot["unit_cost"])
                realized_profit = (proceeds_per_share - lot_unit_cost) * consumed_quantity

                lot["quantity"] = max(0.0, lot_quantity - consumed_quantity)
                remaining_quantity -= consumed_quantity

                total_realized[position_currency] += realized_profit
                group_realized[str(lot["group"])] += realized_profit

            lot_inventory[position_key][position_currency] = [
                lot for lot in lots if float(lot["quantity"]) > 1e-9
            ]

    today = date.today()
    for (symbol, market, account_type), currency_lots in lot_inventory.items():
        for currency, lots in currency_lots.items():
            applied_key = (symbol, market, account_type, currency)
            applied_split_counts[applied_key] = apply_splits_to_lots(
                lots,
                split_schedule.get((symbol, market.value), []),
                applied_split_counts[applied_key],
                today,
            )

    position_currency_totals: dict[
        tuple[str, Market, Currency], dict[str, float]
    ] = defaultdict(lambda: {"quantity": 0.0, "total_cost": 0.0, "realized_pl": 0.0})
    position_group_totals: dict[
        tuple[str, Market, Currency, str], dict[str, float]
    ] = defaultdict(lambda: {"quantity": 0.0, "total_cost": 0.0, "realized_pl": 0.0})

    for (symbol, market, _account_type), currency_lots in lot_inventory.items():
        total_realized_map = realized_totals[(symbol, market, _account_type)]
        group_realized_map = realized_by_group[(symbol, market, _account_type)]
        for currency, lots in currency_lots.items():
            total_key = (symbol, market, currency)
            position_currency_totals[total_key]["quantity"] += sum(
                float(lot["quantity"]) for lot in lots
            )
            position_currency_totals[total_key]["total_cost"] += sum(
                float(lot["quantity"]) * float(lot["unit_cost"]) for lot in lots
            )
            position_currency_totals[total_key]["realized_pl"] += total_realized_map[currency]

            grouped_lots: defaultdict[str, dict[str, float]] = defaultdict(
                lambda: {"quantity": 0.0, "total_cost": 0.0}
            )
            for lot in lots:
                group_name = str(lot["group"])
                grouped_lots[group_name]["quantity"] += float(lot["quantity"])
                grouped_lots[group_name]["total_cost"] += float(lot["quantity"]) * float(
                    lot["unit_cost"]
                )

            funding_groups = set(grouped_lots.keys()) | set(group_realized_map[currency].keys())
            for funding_group in funding_groups:
                group_key = (symbol, market, currency, funding_group)
                position_group_totals[group_key]["quantity"] += grouped_lots[funding_group][
                    "quantity"
                ]
                position_group_totals[group_key]["total_cost"] += grouped_lots[funding_group][
                    "total_cost"
                ]
                position_group_totals[group_key]["realized_pl"] += group_realized_map[currency][
                    funding_group
                ]

    if realized_pnl_records is not None:
        for totals in position_currency_totals.values():
            totals["realized_pl"] = 0.0
        for totals in position_group_totals.values():
            totals["realized_pl"] = 0.0

        for record in realized_pnl_records:
            total_key = (record.symbol, record.market, record.position_currency)
            position_currency_totals[total_key]["realized_pl"] += record.realized_pl
            for allocation in record.allocations:
                group_key = (
                    record.symbol,
                    record.market,
                    record.position_currency,
                    allocation.funding_group,
                )
                position_group_totals[group_key]["realized_pl"] += allocation.realized_pl

    positions: list[Position] = []
    position_keys = sorted(
        {(symbol, market) for symbol, market, _currency in position_currency_totals.keys()},
        key=lambda item: (item[0], item[1].value),
    )
    for symbol, market in position_keys:
        breakdown: list[PositionBreakdown] = []
        group_breakdown: list[PositionGroupBreakdown] = []
        currencies = sorted(
            currency
            for current_symbol, current_market, currency in position_currency_totals.keys()
            if current_symbol == symbol and current_market == market
        )

        for currency in currencies:
            totals = position_currency_totals[(symbol, market, currency)]
            total_qty = totals["quantity"]
            total_cost = totals["total_cost"]
            avg_cost = total_cost / total_qty if total_qty else 0.0

            quote = quote_map.get((symbol, market))
            current_price = (
                quote.price if quote and quote.currency == currency else None
            )
            unrealized_pl = (
                (current_price - avg_cost) * total_qty
                if current_price is not None and total_qty
                else None
            )

            breakdown.append(
                PositionBreakdown(
                    currency=currency,
                    quantity=round(total_qty, 4),
                    average_cost=round(avg_cost, 4),
                    realized_pl=round(totals["realized_pl"], 2),
                    current_price=round(current_price, 4) if current_price is not None else None,
                    unrealized_pl=round(unrealized_pl, 2) if unrealized_pl is not None else None,
                )
            )

            group_keys = sorted(
                funding_group
                for current_symbol, current_market, current_currency, funding_group in position_group_totals.keys()
                if current_symbol == symbol and current_market == market and current_currency == currency
            )

            for funding_group in group_keys:
                record = position_group_totals[(symbol, market, currency, funding_group)]
                qty = record["quantity"]
                realized_value = record["realized_pl"]
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
                market=market,
                breakdown=breakdown,
                group_breakdown=group_breakdown,
            )
        )
    return positions

def compute_fund_snapshots(
    transactions: Iterable[Transaction],
    funding_groups: Iterable[FundingGroup],
    tax_settlements: Iterable[TaxSettlementRecord] | None = None,
    annual_tax_settlements: Iterable[AnnualTaxSettlement] | None = None,
    capital_adjustments: Iterable[FundingCapitalAdjustment] | None = None,
    fx_exchanges: Iterable[FxExchangeRecord] | None = None,
    stock_splits: Iterable[StockSplitRecord] | None = None,
    realized_pnl_records: Iterable[RealizedPnLRecord] | None = None,
    cash_activities: Iterable[CashActivity] | None = None,
) -> FundSnapshots:
    group_lookup = {group.name: group for group in funding_groups}
    fx_records = list(fx_exchanges or [])
    fx_map = _fx_lookup(fx_records)
    split_schedule = build_split_schedule(stock_splits or [])
    standalone_fx_records = [item for item in fx_records if not item.transaction_id]
    sorted_transactions = [
        tx
        for _, tx in sorted(
            enumerate(transactions),
            key=lambda pair: (pair[1].trade_date, pair[0]),
        )
    ]
    settlements = list(tax_settlements or [])
    annual_settlements = list(annual_tax_settlements or [])
    adjustments = list(capital_adjustments or [])
    cash_records = list(cash_activities or [])
    groups_by_currency: dict[Currency, list[str]] = defaultdict(list)
    for name, group in group_lookup.items():
        groups_by_currency[group.currency].append(name)

    def cash_activity_group(item: CashActivity) -> str | None:
        if item.currency is None:
            return None
        candidates = groups_by_currency.get(item.currency, [])
        if item.currency.value in candidates:
            return item.currency.value
        return candidates[0] if len(candidates) == 1 else None

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
        report_contributions: defaultdict[str, float] = defaultdict(float)
        inventories: dict[str, dict[tuple[str, Market], dict[str, float]]] = {}
        position_lots: dict[tuple[str, Market, str], list[dict[str, float | str]]] = defaultdict(list)
        applied_split_counts: dict[tuple[str, Market, str], int] = defaultdict(int)
        cutoff = until or today

        def sync_group_quantities(position_key: tuple[str, Market, str]) -> None:
            group_quantities: defaultdict[str, float] = defaultdict(float)
            for lot in position_lots[position_key]:
                group_quantities[str(lot["group"])] += float(lot["quantity"])
            for group_name, group_inventory in inventories.items():
                record = group_inventory.get(position_key)
                if record is not None:
                    record["quantity"] = group_quantities.get(group_name, 0.0)

        for tx in sorted_transactions:
            if until and tx.trade_date > until:
                continue
            cash_group_name = tx.settlement_group or tx.funding_group
            amount = tx.settlement_amount or tx.gross_amount
            group = group_lookup.get(cash_group_name)
            if not group:
                raise ValueError(f"Funding group not found for transaction {tx.id}")
            group_currency = group.currency
            cash_currency = tx.settlement_currency or tx.cash_currency
            if tx.cross_currency and cash_currency != group_currency:
                fx_record = fx_map.get(tx.id)
                if not fx_record:
                    raise ValueError(
                        f"FX exchange required for transaction {tx.id} ({tx.symbol})"
                    )
                if {
                    fx_record.from_currency,
                    fx_record.to_currency,
                } != {cash_currency, group_currency}:
                    raise ValueError(
                        f"FX exchange currency mismatch for transaction {tx.id}"
                    )
                amount = _convert_with_rate(
                    amount=amount,
                    from_currency=cash_currency,
                    to_currency=group_currency,
                    rate=fx_record.rate,
                )
            if tx.quantity > 0:
                cash_flows[cash_group_name] -= amount
            else:
                cash_flows[cash_group_name] += amount

            position_group_name = tx.position_group or tx.funding_group
            position_group = group_lookup.get(position_group_name)
            if not position_group:
                raise ValueError(f"Position group not found for transaction {tx.id}")
            position_key = _position_account_key(tx)
            previous_split_count = applied_split_counts[position_key]
            applied_split_counts[position_key] = apply_splits_to_lots(
                position_lots[position_key],
                split_schedule.get((tx.symbol, tx.market.value), []),
                previous_split_count,
                tx.trade_date,
            )
            if applied_split_counts[position_key] != previous_split_count:
                sync_group_quantities(position_key)
            holding_amount = amount
            if tx.trade_currency and tx.trade_currency != position_group.currency:
                holding_amount = tx.settlement_amount or amount

            group_inventory = inventories.setdefault(position_group_name, {})
            record = group_inventory.setdefault(
                position_key,
                {
                    "quantity": 0.0,
                    "total_cost": 0.0,
                },
            )

            if tx.quantity > 0:
                record["quantity"] += tx.quantity
                record["total_cost"] += holding_amount
                unit_cost = holding_amount / tx.quantity if tx.quantity else 0.0
                position_lots[position_key].append(
                    {
                        "group": position_group_name,
                        "quantity": tx.quantity,
                        "unit_cost": unit_cost,
                    }
                )
            else:
                remaining_quantity = -tx.quantity
                for lot in position_lots[position_key]:
                    lot_quantity = float(lot["quantity"])
                    if lot_quantity <= 1e-9 or remaining_quantity <= 1e-9:
                        continue

                    consumed_quantity = min(remaining_quantity, lot_quantity)
                    consumed_cost = float(lot["unit_cost"]) * consumed_quantity
                    lot["quantity"] = max(0.0, lot_quantity - consumed_quantity)
                    remaining_quantity -= consumed_quantity

                    lot_group_name = str(lot["group"])
                    lot_group_inventory = inventories.setdefault(lot_group_name, {})
                    lot_record = lot_group_inventory.setdefault(
                        position_key,
                        {"quantity": 0.0, "total_cost": 0.0},
                    )
                    lot_record["quantity"] = max(0.0, lot_record["quantity"] - consumed_quantity)
                    lot_record["total_cost"] = max(0.0, lot_record["total_cost"] - consumed_cost)

                position_lots[position_key] = [
                    lot for lot in position_lots[position_key] if float(lot["quantity"]) > 1e-9
                ]

        for position_key, lots in position_lots.items():
            symbol, market, _account_type = position_key
            applied_split_counts[position_key] = apply_splits_to_lots(
                lots,
                split_schedule.get((symbol, market.value), []),
                applied_split_counts[position_key],
                cutoff,
            )
            sync_group_quantities(position_key)

        for fx_entry in standalone_fx_records:
            if until and fx_entry.exchange_date > until:
                continue
            from_group_name = _resolve_fx_group_name(group_lookup, fx_entry.from_currency)
            to_group_name = _resolve_fx_group_name(group_lookup, fx_entry.to_currency)
            cash_flows[from_group_name] -= fx_entry.from_amount
            cash_flows[to_group_name] += fx_entry.to_amount

        for cash_entry in cash_records:
            if until and cash_entry.activity_date > until:
                continue
            group_name = cash_activity_group(cash_entry)
            if group_name is None:
                continue
            signed_amount = (
                cash_entry.amount
                if cash_entry.direction == CashDirection.IN
                else -cash_entry.amount
            )
            if cash_entry.category == CashActivityCategory.EXTERNAL_TRANSFER:
                report_contributions[group_name] += signed_amount
            elif cash_entry.category in {
                CashActivityCategory.TAX,
                CashActivityCategory.DIVIDEND,
            }:
                cash_flows[group_name] += signed_amount

        if settlements:
            for entry in settlements:
                if until and entry.recorded_at > until:
                    continue
                cash_flows[entry.funding_group] -= entry.jpy_equivalent or entry.amount

        cutoff_year = cutoff.year
        for entry in annual_settlements:
            if entry.year > cutoff_year:
                continue
            cash_flows[entry.funding_group] -= entry.amount

        state: dict[str, dict[str, float]] = {}
        for name, group in group_lookup.items():
            delta = cash_flows.get(name, 0.0)
            contributions = sum(
                adjustment.amount
                for adjustment in adjustments_by_group.get(name, [])
                if adjustment.effective_date <= cutoff
            ) + report_contributions.get(name, 0.0)
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

    realized_years_by_group: dict[str, defaultdict[int, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    if realized_pnl_records is not None:
        for record in realized_pnl_records:
            target_year = record.trade_date.year
            canonical_groups = groups_by_currency.get(record.position_currency, [])
            canonical_group = canonical_groups[0] if len(canonical_groups) == 1 else None
            allocated_amount = 0.0

            for allocation in record.allocations:
                allocation_group = allocation.funding_group
                target_group: str | None = None
                group = group_lookup.get(allocation_group)
                if group and group.currency == record.position_currency:
                    target_group = allocation_group
                elif canonical_group:
                    target_group = canonical_group

                if target_group is None:
                    continue

                realized_years_by_group[target_group][target_year] += allocation.realized_pl
                allocated_amount += allocation.realized_pl

            if not record.allocations and canonical_group:
                realized_years_by_group[canonical_group][target_year] += record.realized_pl
            elif canonical_group and abs(record.realized_pl - allocated_amount) > 1e-6:
                realized_years_by_group[canonical_group][target_year] += (
                    record.realized_pl - allocated_amount
                )

        for entry in settlements:
            realized_years_by_group[entry.funding_group][entry.recorded_at.year] -= (
                entry.jpy_equivalent or entry.amount
            )

        for entry in annual_settlements:
            realized_years_by_group[entry.funding_group][entry.year] -= entry.amount

        for entry in cash_records:
            group_name = cash_activity_group(entry)
            if group_name is None or entry.category not in {
                CashActivityCategory.TAX,
                CashActivityCategory.DIVIDEND,
            }:
                continue
            signed_amount = entry.amount if entry.direction == CashDirection.IN else -entry.amount
            realized_years_by_group[group_name][entry.activity_date.year] += signed_amount

    snapshots: list[FundSnapshot] = []
    for name, group in group_lookup.items():
        final_metrics = final_state[name]
        last_year_metrics = last_year_state[name]
        prev_year_metrics = prev_year_state[name]

        if realized_pnl_records is not None:
            current_year_pl = realized_years_by_group[name][today.year]
            previous_year_pl = realized_years_by_group[name][today.year - 1]
        else:
            # Remove net capital additions so realized profits are not inflated by fresh funding.
            raw_current_year_pl = final_metrics["current_total"] - last_year_metrics["current_total"]
            current_year_contributions = (
                final_metrics["contributions"] - last_year_metrics["contributions"]
            )
            current_year_pl = raw_current_year_pl - current_year_contributions

            raw_previous_year_pl = (
                last_year_metrics["current_total"] - prev_year_metrics["current_total"]
            )
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
    payer_group = repo.get_funding_group(payload.funding_group)
    if payer_group.currency != Currency.JPY:
        raise ValueError("Tax payments must be made from a JPY funding group")

    if transaction.cash_currency == Currency.USD and not payload.balance_exchange_rate:
        raise ValueError("balance_exchange_rate is required for USD transactions")

    repo.mark_transaction_taxed(payload.transaction_id)
    record = TaxSettlementRecord(
        id=str(uuid4()),
        transaction_id=payload.transaction_id,
        amount=payload.amount,
        currency=payload.currency,
        exchange_rate=payload.exchange_rate,
        funding_group=payload.funding_group,
        jpy_equivalent=None,
        balance_exchange_rate=payload.balance_exchange_rate,
        balance_usd_required=None,
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
    group = repo.get_funding_group(funding_group)
    if group.currency != Currency.JPY:
        raise ValueError("Tax payments must be made from a JPY funding group")

    amount = payload.amount or original.amount
    exchange_rate = payload.exchange_rate
    if exchange_rate is None and original.exchange_rate is not None:
        exchange_rate = original.exchange_rate
    balance_exchange_rate = payload.balance_exchange_rate
    if balance_exchange_rate is None and original.balance_exchange_rate is not None:
        balance_exchange_rate = original.balance_exchange_rate

    if transaction.cash_currency == Currency.USD and not balance_exchange_rate:
        raise ValueError("balance_exchange_rate is required for USD transactions")

    updated_record = TaxSettlementRecord(
        id=original.id,
        transaction_id=original.transaction_id,
        amount=amount,
        currency=original.currency,
        exchange_rate=exchange_rate,
        funding_group=funding_group,
        jpy_equivalent=None,
        balance_exchange_rate=balance_exchange_rate,
        balance_usd_required=None,
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
    funding_group = selected[0].position_group or selected[0].funding_group
    market = selected[0].market
    currency = selected[0].settlement_currency or selected[0].cash_currency

    for tx in selected:
        if tx.symbol != symbol:
            raise ValueError("Selected transactions must share the same symbol")
        if (tx.position_group or tx.funding_group) != funding_group:
            raise ValueError("Selected transactions must use the same funding group")
        if tx.market != market:
            raise ValueError("Selected transactions must belong to the same market")
        if (tx.settlement_currency or tx.cash_currency) != currency:
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
    total_buy_amount = sum((tx.settlement_amount or tx.gross_amount) for tx in buys)
    total_sell_amount = sum((tx.settlement_amount or tx.gross_amount) for tx in sells)

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
