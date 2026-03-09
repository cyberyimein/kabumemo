from __future__ import annotations

from collections import defaultdict
from typing import Iterable
from uuid import uuid4

from ..models.schemas import (
    Currency,
    FxExchangeRecord,
    RealizedPnLAllocation,
    RealizedPnLRecord,
    StockSplitRecord,
    Transaction,
)
from .stock_splits import apply_splits_to_lots, build_split_schedule


def _market_currency(market: str) -> Currency:
    return Currency.USD if str(market) == "US" else Currency.JPY


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


def _position_currency_for_transaction(tx: Transaction) -> Currency:
    if (
        not tx.cross_currency
        and tx.trade_amount == tx.gross_amount
        and tx.settlement_currency == tx.cash_currency
        and tx.cash_currency != _market_currency(tx.market.value)
    ):
        return tx.cash_currency
    return tx.trade_currency or (
        tx.buy_currency if tx.cross_currency and tx.buy_currency else tx.cash_currency
    )


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


def rebuild_realized_pnl_records(
    transactions: Iterable[Transaction],
    fx_exchanges: Iterable[FxExchangeRecord] | None = None,
    stock_splits: Iterable[StockSplitRecord] | None = None,
) -> list[RealizedPnLRecord]:
    fx_map = _fx_lookup(fx_exchanges or [])
    split_schedule = build_split_schedule(stock_splits or [])
    lot_inventory: dict[
        tuple[str, str, str, Currency], list[dict[str, float | str]]
    ] = defaultdict(list)
    applied_split_counts: dict[tuple[str, str, str, Currency], int] = defaultdict(int)
    sorted_transactions = [
        tx
        for _, tx in sorted(
            enumerate(transactions),
            key=lambda pair: (pair[1].trade_date, pair[0]),
        )
    ]
    records: list[RealizedPnLRecord] = []

    for tx in sorted_transactions:
        position_currency = _position_currency_for_transaction(tx)
        position_key = (tx.symbol, tx.market.value, tx.broker_account_type.value, position_currency)
        lots = lot_inventory[position_key]
        applied_split_counts[position_key] = apply_splits_to_lots(
            lots,
            split_schedule.get((tx.symbol, tx.market.value), []),
            applied_split_counts[position_key],
            tx.trade_date,
        )
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
            continue

        sell_quantity = -tx.quantity
        if sell_quantity <= 0:
            continue

        remaining_quantity = sell_quantity
        proceeds_per_share = effective_amount / sell_quantity if sell_quantity else 0.0
        allocations: dict[str, dict[str, float]] = defaultdict(
            lambda: {"quantity": 0.0, "cost_basis": 0.0, "realized_pl": 0.0}
        )
        total_cost_basis = 0.0
        total_realized = 0.0

        for lot in lots:
            lot_quantity = float(lot["quantity"])
            if lot_quantity <= 1e-9 or remaining_quantity <= 1e-9:
                continue

            consumed_quantity = min(remaining_quantity, lot_quantity)
            lot_unit_cost = float(lot["unit_cost"])
            cost_basis = lot_unit_cost * consumed_quantity
            realized_profit = (proceeds_per_share - lot_unit_cost) * consumed_quantity
            funding_group = str(lot["group"])

            allocations[funding_group]["quantity"] += consumed_quantity
            allocations[funding_group]["cost_basis"] += cost_basis
            allocations[funding_group]["realized_pl"] += realized_profit

            total_cost_basis += cost_basis
            total_realized += realized_profit

            lot["quantity"] = max(0.0, lot_quantity - consumed_quantity)
            remaining_quantity -= consumed_quantity

        lot_inventory[position_key] = [
            lot for lot in lots if float(lot["quantity"]) > 1e-9
        ]

        records.append(
            RealizedPnLRecord(
                id=str(uuid4()),
                sell_transaction_id=tx.id,
                trade_date=tx.trade_date,
                symbol=tx.symbol,
                market=tx.market,
                broker_account_type=tx.broker_account_type,
                position_currency=position_currency,
                settlement_currency=tx.settlement_currency or tx.cash_currency,
                quantity=round(sell_quantity, 4),
                matched_quantity=round(sell_quantity - remaining_quantity, 4),
                unmatched_quantity=round(max(0.0, remaining_quantity), 4),
                proceeds_amount=round(effective_amount, 4),
                cost_basis=round(total_cost_basis, 4),
                realized_pl=round(total_realized, 4),
                allocations=[
                    RealizedPnLAllocation(
                        funding_group=funding_group,
                        quantity=round(values["quantity"], 4),
                        cost_basis=round(values["cost_basis"], 4),
                        realized_pl=round(values["realized_pl"], 4),
                    )
                    for funding_group, values in sorted(allocations.items())
                ],
                memo=tx.memo,
            )
        )

    return records


def rebuild_and_persist_realized_pnl(repository, transactions: Iterable[Transaction] | None = None) -> list[RealizedPnLRecord]:
    source_transactions = list(transactions) if transactions is not None else repository.list_transactions()
    fx_exchanges = repository.list_fx_exchanges()
    stock_splits = repository.list_stock_splits()
    records = rebuild_realized_pnl_records(source_transactions, fx_exchanges, stock_splits)
    repository.replace_realized_pnl_records(records)
    return records