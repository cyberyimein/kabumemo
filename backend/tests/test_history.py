from __future__ import annotations

from datetime import date

import pytest # type: ignore

from app.models.schemas import Currency, FxExchangeRecord, Market, TradeSide, Transaction
from app.services import history


def make_transaction(**overrides) -> Transaction:
    payload = {
        "id": "tx-1",
        "trade_date": date(2025, 1, 10),
        "symbol": "XPEV",
        "quantity": 10.0,
        "gross_amount": 1000.0,
        "funding_group": "JPY",
        "cash_currency": Currency.USD,
        "market": Market.US,
        "taxed": "Y",
        "memo": None,
    }
    payload.update(overrides)
    return Transaction(**payload)


def make_fx(transaction_id: str, rate: float = 150.0) -> FxExchangeRecord:
    return FxExchangeRecord(
        id="fx-1",
        transaction_id=transaction_id,
        exchange_date=date(2025, 1, 10),
        from_currency=Currency.JPY,
        to_currency=Currency.USD,
        from_amount=150000.0,
        to_amount=1000.0,
        rate=rate,
        notes=None,
    )


def test_build_trade_markers_converts_fx():
    tx = make_transaction(
        symbol="XPEV",
        quantity=10.0,
        gross_amount=150000.0,
        cash_currency=Currency.JPY,
        market=Market.US,
    )
    fx = make_fx(tx.id, rate=150.0)

    markers = history.build_trade_markers([tx], [fx], symbol="XPEV", market=Market.US)

    assert len(markers) == 1
    marker = markers[0]
    assert marker.currency == Currency.USD
    assert marker.side == TradeSide.BUY
    assert marker.price == pytest.approx(100.0)


def test_get_position_history_includes_markers(monkeypatch):
    series = [history.PriceHistoryPoint(date=date(2025, 1, 2), close=101.5)]

    def fake_fetch(symbol: str, market: Market, period: str = "1y"):
        return series

    monkeypatch.setattr(history, "fetch_price_history", fake_fetch)

    tx = make_transaction(symbol="XPEV", quantity=-5.0, gross_amount=550.0)

    response = history.get_position_history(
        transactions=[tx],
        fx_exchanges=[],
        symbol="XPEV",
        market=Market.US,
        period="1y",
    )

    assert response.series == series
    assert len(response.markers) == 1
    marker = response.markers[0]
    assert marker.side == TradeSide.SELL
    assert marker.price == pytest.approx(110.0)
