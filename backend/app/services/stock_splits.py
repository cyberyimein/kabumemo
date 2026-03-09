from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from ..models.schemas import Market, StockSplitRecord, Transaction


def normalize_symbol(symbol: str, market: Market | str) -> str:
    normalized = symbol.strip().upper()
    market_value = market.value if isinstance(market, Market) else str(market)
    if market_value == Market.JP.value and normalized and not normalized.endswith(".T"):
        normalized = f"{normalized}.T"
    return normalized


def split_factor(split: StockSplitRecord) -> float:
    return split.ratio_after / split.ratio_before


def build_split_schedule(
    stock_splits: Iterable[StockSplitRecord],
) -> dict[tuple[str, str], list[StockSplitRecord]]:
    schedule: dict[tuple[str, str], list[StockSplitRecord]] = defaultdict(list)
    for split in stock_splits:
        key = (normalize_symbol(split.symbol, split.market), split.market.value)
        schedule[key].append(split)
    for items in schedule.values():
        items.sort(key=lambda item: (item.effective_date, item.id))
    return schedule


def apply_splits_to_lots(
    lots: list[dict[str, float | str]],
    split_records: list[StockSplitRecord],
    applied_count: int,
    until: date,
) -> int:
    next_index = applied_count
    while next_index < len(split_records):
        split = split_records[next_index]
        if split.effective_date > until:
            break
        factor = split_factor(split)
        for lot in lots:
            quantity = float(lot["quantity"])
            unit_cost = float(lot["unit_cost"])
            lot["quantity"] = quantity * factor
            lot["unit_cost"] = unit_cost / factor
        next_index += 1
    return next_index


def adjusted_quantity_for_date(
    tx: Transaction,
    stock_splits: Iterable[StockSplitRecord],
    as_of: date,
) -> float:
    quantity = tx.quantity
    normalized_symbol = normalize_symbol(tx.symbol, tx.market)
    for split in stock_splits:
        if normalize_symbol(split.symbol, split.market) != normalized_symbol:
            continue
        if split.market != tx.market:
            continue
        if tx.trade_date < split.effective_date <= as_of:
            quantity *= split_factor(split)
    return quantity