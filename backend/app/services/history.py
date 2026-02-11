from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd
import yfinance as yf

from ..models.schemas import (
    Currency,
    FxExchangeRecord,
    Market,
    PositionHistoryResponse,
    PriceHistoryPoint,
    TradeMarker,
    TradeSide,
    Transaction,
)


def _market_currency(market: Market) -> Currency:
    return Currency.USD if market == Market.US else Currency.JPY


def _extract_close_series(data: pd.DataFrame | None, ticker: str) -> pd.Series:
    if not isinstance(data, pd.DataFrame) or data.empty:
        return pd.Series(dtype=float)
    if "Close" in data.columns:
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            first_col = close.columns[0]
            return close[first_col]
        return close
    if ticker in data.columns:
        symbol_frame = data[ticker]
        if isinstance(symbol_frame, pd.DataFrame) and "Close" in symbol_frame:
            close = symbol_frame["Close"]
            if isinstance(close, pd.DataFrame):
                first_col = close.columns[0]
                return close[first_col]
            return close
        if isinstance(symbol_frame, pd.Series):
            return symbol_frame
    return pd.Series(dtype=float)


def fetch_price_history(symbol: str, market: Market, period: str = "1y") -> list[PriceHistoryPoint]:
    normalized = period.strip().lower() if period else "1y"
    if normalized not in {"1y", "1yr", "1year"}:
        normalized = "1y"

    ticker = symbol
    try:
        data = yf.download(tickers=ticker, period=normalized, interval="1d", progress=False)
    except Exception:
        return []
    close_series = _extract_close_series(data, ticker).dropna()
    if close_series.empty:
        return []

    points: list[PriceHistoryPoint] = []
    for timestamp, value in close_series.items():
        if pd.isna(value):
            continue
        ts = pd.Timestamp(timestamp)
        point_date = ts.date()
        points.append(PriceHistoryPoint(date=point_date, close=round(float(value), 6)))
    return points


def _convert_amount(amount: float, from_currency: Currency, to_currency: Currency, rate: float) -> float:
    if from_currency == to_currency:
        return amount
    if from_currency == Currency.JPY and to_currency == Currency.USD:
        return amount / rate
    if from_currency == Currency.USD and to_currency == Currency.JPY:
        return amount * rate
    return amount


def build_trade_markers(
    transactions: Iterable[Transaction],
    fx_exchanges: Iterable[FxExchangeRecord],
    symbol: str,
    market: Market,
) -> list[TradeMarker]:
    market_currency = _market_currency(market)
    fx_map = {fx.transaction_id: fx for fx in fx_exchanges if fx.transaction_id}
    markers: list[TradeMarker] = []

    for tx in transactions:
        if tx.symbol != symbol or tx.market != market:
            continue
        quantity = abs(tx.quantity)
        if quantity <= 0:
            continue
        amount = tx.gross_amount
        currency = tx.cash_currency

        if tx.cash_currency != market_currency:
            fx = fx_map.get(tx.id)
            if fx and {fx.from_currency, fx.to_currency} == {tx.cash_currency, market_currency}:
                amount = _convert_amount(amount, tx.cash_currency, market_currency, fx.rate)
                currency = market_currency

        price = amount / quantity
        markers.append(
            TradeMarker(
                date=tx.trade_date,
                price=round(float(price), 6),
                side=TradeSide.BUY if tx.quantity > 0 else TradeSide.SELL,
                quantity=round(float(quantity), 6),
                currency=currency,
                transaction_id=tx.id,
            )
        )

    markers.sort(key=lambda item: (item.date, item.transaction_id))
    return markers


def get_position_history(
    *,
    transactions: Iterable[Transaction],
    fx_exchanges: Iterable[FxExchangeRecord],
    symbol: str,
    market: Market,
    period: str = "1y",
) -> PositionHistoryResponse:
    series = fetch_price_history(symbol, market, period=period)
    markers = build_trade_markers(transactions, fx_exchanges, symbol, market)
    currency = _market_currency(market)

    return PositionHistoryResponse(
        symbol=symbol,
        market=market,
        currency=currency,
        series=series,
        markers=markers,
    )
