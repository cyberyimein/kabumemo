from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd
import yfinance as yf

from ..models.schemas import Currency, Market, QuoteRecord, QuoteSnapshot, Transaction
from ..storage.repository import LocalDataRepository


def _symbol_key(transaction: Transaction) -> str:
    return f"{transaction.symbol}|{transaction.market.value}"


def _market_currency(market: Market) -> Currency:
    return Currency.USD if market == Market.US else Currency.JPY


def _collect_symbols(transactions: Iterable[Transaction]) -> list[tuple[str, Market]]:
    seen: set[str] = set()
    symbols: list[tuple[str, Market]] = []
    for tx in transactions:
        key = _symbol_key(tx)
        if key in seen:
            continue
        seen.add(key)
        symbols.append((tx.symbol, tx.market))
    return symbols


def _fetch_prices(symbols: list[tuple[str, Market]]) -> list[QuoteRecord]:
    if not symbols:
        return []
    tickers = " ".join(symbol for symbol, _ in symbols)
    data = yf.download(tickers=tickers, period="1d", interval="1d", group_by="ticker", progress=False)
    if data is None or (isinstance(data, pd.DataFrame) and data.empty):
        return []
    records: list[QuoteRecord] = []
    today = date.today()

    for symbol, market in symbols:
        price = None
        if len(symbols) == 1:
            if isinstance(data, pd.DataFrame) and "Close" in data.columns:
                close_series = data["Close"]
                if not close_series.empty:
                    price = float(close_series.iloc[-1])
        else:
            if isinstance(data, pd.DataFrame) and symbol in data.columns:
                symbol_frame = data[symbol]
                if "Close" in symbol_frame and not symbol_frame["Close"].empty:
                    price = float(symbol_frame["Close"].iloc[-1])
        if price is None:
            continue
        records.append(
            QuoteRecord(
                symbol=symbol,
                market=market,
                price=round(price, 6),
                currency=_market_currency(market),
                as_of=today,
            )
        )
    return records


def refresh_quotes_if_needed(repo: LocalDataRepository, force: bool = False) -> QuoteSnapshot:
    existing = repo.list_quotes()
    today = date.today()
    if existing and not force and all(record.as_of == today for record in existing):
        return QuoteSnapshot(as_of=today, records=existing)

    transactions = repo.list_transactions()
    symbols = _collect_symbols(transactions)
    records = _fetch_prices(symbols)
    repo.replace_quotes(records)
    return QuoteSnapshot(as_of=today, records=records)
