from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from ..models.schemas import (
    Market,
    StockSplitCandidate,
    StockSplitDetectionResponse,
    StockSplitRecord,
    Transaction,
)
from .stock_splits import adjusted_quantity_for_date, normalize_symbol


def _fetch_split_events(symbol: str, start: date) -> list[tuple[date, float]]:
    """Return explicit corporate-action split events; never infer from price gaps."""
    try:
        history = yf.Ticker(symbol).history(
            start=start.isoformat(),
            end=(date.today() + timedelta(days=1)).isoformat(),
            actions=True,
            auto_adjust=False,
        )
    except Exception:
        raise RuntimeError(f"Unable to load corporate actions for {symbol}")

    if not isinstance(history, pd.DataFrame) or history.empty or "Stock Splits" not in history:
        return []

    events: list[tuple[date, float]] = []
    for timestamp, raw_ratio in history["Stock Splits"].items():
        if pd.isna(raw_ratio):
            continue
        ratio = float(raw_ratio)
        if ratio <= 0 or abs(ratio - 1.0) <= 1e-9:
            continue
        events.append((pd.Timestamp(timestamp).date(), ratio))
    return events


def detect_stock_split_candidates(
    transactions: list[Transaction],
    recorded_splits: list[StockSplitRecord],
) -> StockSplitDetectionResponse:
    by_symbol: dict[tuple[str, Market], list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        symbol = normalize_symbol(transaction.symbol, transaction.market)
        by_symbol[(symbol, transaction.market)].append(transaction)

    recorded_keys = {
        (
            normalize_symbol(split.symbol, split.market),
            split.market,
            split.effective_date,
        )
        for split in recorded_splits
    }
    candidates: list[StockSplitCandidate] = []
    failed_symbols: list[str] = []

    for (symbol, market), symbol_transactions in sorted(
        by_symbol.items(), key=lambda item: item[0][0]
    ):
        first_trade_date = min(item.trade_date for item in symbol_transactions)
        try:
            events = _fetch_split_events(symbol, first_trade_date)
        except RuntimeError:
            failed_symbols.append(symbol)
            continue

        for effective_date, ratio in events:
            if (symbol, market, effective_date) in recorded_keys:
                continue
            quantity_before = sum(
                adjusted_quantity_for_date(transaction, recorded_splits, effective_date)
                for transaction in symbol_transactions
                if transaction.trade_date < effective_date
            )
            if abs(quantity_before) <= 1e-9:
                continue
            suggested_quantity_after = quantity_before * ratio
            candidates.append(
                StockSplitCandidate(
                    symbol=symbol,
                    market=market,
                    effective_date=effective_date,
                    ratio_before=1.0,
                    ratio_after=ratio,
                    notes="Detected from Yahoo Finance corporate actions",
                    quantity_before=round(quantity_before, 6),
                    suggested_quantity_after=round(suggested_quantity_after, 6),
                    quantity_delta=round(suggested_quantity_after - quantity_before, 6),
                )
            )

    candidates.sort(key=lambda item: (item.effective_date, item.symbol), reverse=True)
    return StockSplitDetectionResponse(
        candidates=candidates,
        scanned_symbols=len(by_symbol),
        failed_symbols=failed_symbols,
    )
