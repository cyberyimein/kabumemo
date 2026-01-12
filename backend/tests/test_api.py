from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest # type: ignore
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("KABUCOUNT_DATA_DIR", str(data_dir))

    from app.api import routes  # type: ignore
    from app.main import app  # type: ignore
    from app.storage.repository import LocalDataRepository  # type: ignore

    repository = LocalDataRepository(base_path=data_dir)
    repository.ensure_default_groups()
    routes.repository = repository

    test_client = TestClient(app)
    setattr(test_client, "repository", repository)
    return test_client


def test_transaction_lifecycle(client: TestClient):
    repository = getattr(client, "repository")

    resp = client.get("/api/funding-groups")
    assert resp.status_code == 200
    groups = resp.json()
    assert any(group["name"] == "Default JPY" for group in groups)

    def dump_groups(models):
        return sorted(
            [model.model_dump(mode="json") for model in models],
            key=lambda item: item["name"],
        )

    assert repository.sqlite_has_data()
    assert dump_groups(repository.list_funding_groups()) == dump_groups(
        repository.list_funding_groups_from_sqlite()
    )

    buy_payload = {
        "trade_date": "2025-09-01",
        "symbol": "7203.T",
        "quantity": 10,
        "gross_amount": 150000,
        "funding_group": "Default JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }
    buy_resp = client.post("/api/transactions", json=buy_payload)
    assert buy_resp.status_code == 201, buy_resp.text
    assert buy_resp.json()["taxed"] == "Y"

    sell_payload = {
        "trade_date": "2025-09-15",
        "symbol": "7203.T",
        "quantity": -5,
        "gross_amount": 90000,
        "funding_group": "Default JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }
    sell_resp = client.post("/api/transactions", json=sell_payload)
    assert sell_resp.status_code == 201, sell_resp.text
    sell_body = sell_resp.json()
    assert sell_body["taxed"] == "N"
    sale_id = sell_body["id"]

    update_payload = {
        "trade_date": "2025-09-15",
        "symbol": "7203.T",
        "quantity": -4,
        "gross_amount": 80000,
        "funding_group": "Default JPY",
        "cash_currency": "JPY",
        "market": "JP",
        "taxed": "N",
        "memo": "Adjust lot size",
    }
    update_resp = client.put(f"/api/transactions/{sale_id}", json=update_payload)
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["quantity"] == -4

    taxed_yes_payload = {**update_payload, "taxed": "Y"}
    mark_taxed_resp = client.put(f"/api/transactions/{sale_id}", json=taxed_yes_payload)
    assert mark_taxed_resp.status_code == 200, mark_taxed_resp.text
    assert mark_taxed_resp.json()["taxed"] == "Y"

    revert_untaxed_resp = client.put(f"/api/transactions/{sale_id}", json=update_payload)
    assert revert_untaxed_resp.status_code == 200, revert_untaxed_resp.text
    assert revert_untaxed_resp.json()["taxed"] == "N"

    patch_resp = client.patch(
        f"/api/transactions/{sale_id}",
        json={**update_payload, "taxed": "Y"},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["taxed"] == "Y"

    patch_revert_resp = client.patch(
        f"/api/transactions/{sale_id}",
        json=update_payload,
    )
    assert patch_revert_resp.status_code == 200, patch_revert_resp.text
    assert patch_revert_resp.json()["taxed"] == "N"

    oversell_resp = client.put(
        f"/api/transactions/{sale_id}",
        json={**update_payload, "quantity": -20},
    )
    assert oversell_resp.status_code == 400

    not_found_resp = client.put("/api/transactions/not-found", json=update_payload)
    assert not_found_resp.status_code == 404

    pos_resp = client.get("/api/positions")
    assert pos_resp.status_code == 200
    positions = pos_resp.json()
    jpy_breakdown = positions[0]["breakdown"][0]
    assert jpy_breakdown["quantity"] == 6
    assert jpy_breakdown["realized_pl"] == 20000
    group_breakdown = positions[0]["group_breakdown"]
    assert any(entry["funding_group"] == "Default JPY" for entry in group_breakdown)
    default_group_entry = next(
        entry for entry in group_breakdown if entry["funding_group"] == "Default JPY"
    )
    assert default_group_entry["currency"] == "JPY"
    assert default_group_entry["quantity"] == 6
    assert default_group_entry["average_cost"] == pytest.approx(15000)
    assert default_group_entry["realized_pl"] == pytest.approx(20000)

    funds_resp = client.get("/api/funds")
    assert funds_resp.status_code == 200
    payload = funds_resp.json()
    funds = {item["name"]: item for item in payload["funds"]}
    default_fund = funds["Default JPY"]
    assert default_fund["cash_balance"] == -70000
    assert default_fund["holding_cost"] == 90000
    assert default_fund["current_total"] == 20000
    assert default_fund["total_pl"] == 20000
    assert default_fund["current_year_pl"] == 20000
    assert default_fund["previous_year_pl"] == 0
    assert default_fund["current_year_pl_ratio"] is None
    assert default_fund["previous_year_pl_ratio"] is None

    aggregated = {item["currency"]: item for item in payload["aggregated"]}
    jpy_aggregate = aggregated["JPY"]
    assert jpy_aggregate["group_count"] >= 1
    assert jpy_aggregate["current_total"] == default_fund["current_total"]
    assert jpy_aggregate["total_pl"] == default_fund["total_pl"]
    assert jpy_aggregate["current_year_pl"] == default_fund["current_year_pl"]

    tax_payload = {
        "transaction_id": sale_id,
        "funding_group": "Default JPY",
        "amount": 1000,
        "currency": "JPY",
    }
    tax_resp = client.post("/api/tax/settlements", json=tax_payload)
    assert tax_resp.status_code == 201, tax_resp.text
    tax_body = tax_resp.json()
    assert tax_body["transaction_id"] == sale_id
    assert tax_body["currency"] == "JPY"
    assert tax_body["exchange_rate"] is None
    assert tax_body["jpy_equivalent"] == pytest.approx(1000)
    assert "recorded_at" in tax_body
    settlement_id = tax_body["id"]

    revert_after_settlement = client.put(
        f"/api/transactions/{sale_id}",
        json=update_payload,
    )
    assert revert_after_settlement.status_code == 400
    assert "untaxed" in revert_after_settlement.text

    funds_after_tax = client.get("/api/funds").json()
    funds_map = {item["name"]: item for item in funds_after_tax["funds"]}
    after_tax_default = funds_map["Default JPY"]
    assert after_tax_default["cash_balance"] == -71000
    assert after_tax_default["holding_cost"] == 90000
    assert after_tax_default["current_total"] == 19000
    assert after_tax_default["total_pl"] == 19000
    assert after_tax_default["current_year_pl"] == 19000

    second_tax = client.post("/api/tax/settlements", json=tax_payload)
    assert second_tax.status_code == 400

    settlements_list = client.get("/api/tax/settlements").json()
    assert any(item["id"] == settlement_id for item in settlements_list)

    def dump_transactions(models):
        return sorted(
            [model.model_dump(mode="json") for model in models],
            key=lambda item: item["id"],
        )

    def dump_settlements(models):
        return sorted(
            [model.model_dump(mode="json") for model in models],
            key=lambda item: (item["recorded_at"], item["id"]),
        )

    assert dump_transactions(repository.list_transactions()) == dump_transactions(
        repository.list_transactions_from_sqlite()
    )
    assert dump_settlements(repository.list_tax_settlements()) == dump_settlements(
        repository.list_tax_settlements_from_sqlite()
    )

    delete_resp = client.delete(f"/api/transactions/{sale_id}")
    assert delete_resp.status_code == 204

    remaining_transactions = client.get("/api/transactions").json()
    assert all(tx["id"] != sale_id for tx in remaining_transactions)

    remaining_settlements = client.get("/api/tax/settlements").json()
    assert all(item["transaction_id"] != sale_id for item in remaining_settlements)

    assert dump_transactions(repository.list_transactions()) == dump_transactions(
        repository.list_transactions_from_sqlite()
    )
    assert dump_settlements(repository.list_tax_settlements()) == dump_settlements(
        repository.list_tax_settlements_from_sqlite()
    )

    positions_after_delete = client.get("/api/positions").json()
    post_delete_breakdown = positions_after_delete[0]["breakdown"][0]
    assert post_delete_breakdown["quantity"] == 10
    assert post_delete_breakdown["realized_pl"] == 0
    post_delete_group = positions_after_delete[0]["group_breakdown"]
    assert post_delete_group[0]["funding_group"] == "Default JPY"
    assert post_delete_group[0]["quantity"] == 10
    assert post_delete_group[0]["realized_pl"] == 0

    delete_again = client.delete(f"/api/transactions/{sale_id}")
    assert delete_again.status_code == 404


def test_capital_additions_respected(client: TestClient, monkeypatch):
    from datetime import date as real_date

    import app.services.analytics as analytics

    class FixedDate(real_date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return cls(2025, 12, 15)

    monkeypatch.setattr(analytics, "date", FixedDate)

    future_payload = {
        "amount": 50000,
        "effective_date": "2026-01-01",
        "notes": "next year top-up",
    }
    resp_future = client.post("/api/funding-groups/Default%20JPY/capital", json=future_payload)
    assert resp_future.status_code == 201, resp_future.text

    funds_future = client.get("/api/funds").json()
    future_default = next(item for item in funds_future["funds"] if item["name"] == "Default JPY")
    assert future_default["initial_amount"] == 0
    assert future_default["cash_balance"] == 0
    assert future_default["current_year_pl"] == 0

    current_payload = {
        "amount": 100000,
        "effective_date": "2025-06-01",
        "notes": "mid-year contribution",
    }
    resp_current = client.post("/api/funding-groups/Default%20JPY/capital", json=current_payload)
    assert resp_current.status_code == 201, resp_current.text

    funds_current = client.get("/api/funds").json()
    current_default = next(item for item in funds_current["funds"] if item["name"] == "Default JPY")
    assert current_default["initial_amount"] == 100000
    assert current_default["cash_balance"] == 100000
    assert current_default["total_pl"] == 0
    assert current_default["current_year_pl"] == 0

    aggregated = next(item for item in funds_current["aggregated"] if item["currency"] == "JPY")
    assert aggregated["initial_amount"] >= 100000
    assert aggregated["current_year_pl"] == 0

    repository = getattr(client, "repository")
    json_records = repository.list_capital_adjustments()
    sqlite_records = repository.list_capital_adjustments_from_sqlite()
    assert [r.model_dump(mode="json") for r in json_records] == [
        r.model_dump(mode="json") for r in sqlite_records
    ]

    log_resp = client.get("/api/funding-groups/capital")
    assert log_resp.status_code == 200
    history = log_resp.json()
    assert len(history) == 2
    assert history[0]["effective_date"] == "2025-06-01"
    assert history[1]["effective_date"] == "2026-01-01"


def test_positions_include_pending_sell():
    from datetime import date

    from app.models.schemas import Currency, Market, TaxStatus, Transaction
    from app.services.analytics import compute_positions

    buy = Transaction(
        id="buy-b",
        trade_date=date(2025, 8, 4),
        symbol="8306",
        quantity=100,
        gross_amount=200000,
        funding_group="Default JPY",
        cash_currency=Currency.JPY,
        market=Market.JP,
        taxed=TaxStatus.YES,
        memo=None,
    )
    sell = Transaction(
        id="sell-a",
        trade_date=date(2025, 8, 4),
        symbol="8306",
        quantity=-100,
        gross_amount=210000,
        funding_group="Default JPY",
        cash_currency=Currency.JPY,
        market=Market.JP,
        taxed=TaxStatus.NO,
        memo=None,
    )

    positions = compute_positions([buy, sell])
    assert len(positions) == 1
    position = positions[0]
    assert position.symbol == "8306"
    assert len(position.breakdown) == 1
    component = position.breakdown[0]
    assert component.currency.value == "JPY"
    assert component.quantity == 0
    assert component.realized_pl == 10000
    assert len(position.group_breakdown) == 1
    group_entry = position.group_breakdown[0]
    assert group_entry.funding_group == "Default JPY"
    assert group_entry.currency.value == "JPY"
    assert group_entry.quantity == 0
    assert group_entry.realized_pl == 10000


def test_positions_split_by_currency():
    from datetime import date

    from app.models.schemas import Currency, Market, TaxStatus, Transaction
    from app.services.analytics import compute_positions

    usd_buy = Transaction(
        id="usd-buy",
        trade_date=date(2025, 7, 1),
        symbol="TEST",
        quantity=2,
        gross_amount=200,
        funding_group="USD Group",
        cash_currency=Currency.USD,
        market=Market.US,
        taxed=TaxStatus.YES,
        memo=None,
    )
    usd_sell = Transaction(
        id="usd-sell",
        trade_date=date(2025, 7, 5),
        symbol="TEST",
        quantity=-1,
        gross_amount=150,
        funding_group="USD Group",
        cash_currency=Currency.USD,
        market=Market.US,
        taxed=TaxStatus.NO,
        memo=None,
    )
    jpy_buy = Transaction(
        id="jpy-buy",
        trade_date=date(2025, 7, 2),
        symbol="TEST",
        quantity=3,
        gross_amount=300,
        funding_group="JPY Group",
        cash_currency=Currency.JPY,
        market=Market.US,
        taxed=TaxStatus.YES,
        memo=None,
    )

    positions = compute_positions([usd_buy, usd_sell, jpy_buy])
    assert len(positions) == 1
    position = positions[0]
    assert position.symbol == "TEST"
    assert len(position.breakdown) == 2

    usd_entry = next(item for item in position.breakdown if item.currency == Currency.USD)
    jpy_entry = next(item for item in position.breakdown if item.currency == Currency.JPY)

    assert usd_entry.quantity == 1
    assert usd_entry.average_cost == 100
    assert usd_entry.realized_pl == 50

    assert jpy_entry.quantity == 3
    assert jpy_entry.average_cost == 100
    assert jpy_entry.realized_pl == 0

    assert len(position.group_breakdown) == 2
    usd_group_entry = next(
        item for item in position.group_breakdown if item.funding_group == "USD Group"
    )
    assert usd_group_entry.currency == Currency.USD
    assert usd_group_entry.quantity == 1
    assert usd_group_entry.average_cost == 100
    assert usd_group_entry.realized_pl == 50

    jpy_group_entry = next(
        item for item in position.group_breakdown if item.funding_group == "JPY Group"
    )
    assert jpy_group_entry.currency == Currency.JPY
    assert jpy_group_entry.quantity == 3
    assert jpy_group_entry.average_cost == 100
    assert jpy_group_entry.realized_pl == 0

def test_fund_snapshot_respects_transaction_order():
    from datetime import date

    from app.models.schemas import Currency, FundingGroup, Market, TaxStatus, Transaction
    from app.services.analytics import compute_fund_snapshots

    group = FundingGroup(name="Test Group", currency=Currency.JPY, initial_amount=0)
    buy = Transaction(
        id="tx-b",
        trade_date=date(2025, 1, 2),
        symbol="TEST",
        quantity=1,
        gross_amount=100,
        funding_group=group.name,
        cash_currency=Currency.JPY,
        market=Market.JP,
        taxed=TaxStatus.YES,
        memo=None,
    )
    sell = Transaction(
        id="tx-a",
        trade_date=date(2025, 1, 2),
        symbol="TEST",
        quantity=-1,
        gross_amount=120,
        funding_group=group.name,
        cash_currency=Currency.JPY,
        market=Market.JP,
        taxed=TaxStatus.NO,
        memo=None,
    )

    snapshots = compute_fund_snapshots([buy, sell], [group]).funds
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.holding_cost == 0
    assert snapshot.cash_balance == 20
    assert snapshot.current_total == 20


def test_fund_snapshot_yearly_ratios():
    from datetime import date

    from app.models.schemas import Currency, FundingGroup, Market, TaxStatus, Transaction
    from app.services.analytics import compute_fund_snapshots

    today = date.today()
    current_year = today.year
    previous_year = current_year - 1

    group = FundingGroup(name="Yield Fund", currency=Currency.JPY, initial_amount=1000)
    transactions = [
        Transaction(
            id="buy-prev",
            trade_date=date(previous_year, 1, 10),
            symbol="AAA",
            quantity=1,
            gross_amount=100,
            funding_group=group.name,
            cash_currency=Currency.JPY,
            market=Market.JP,
            taxed=TaxStatus.YES,
            memo=None,
        ),
        Transaction(
            id="sell-prev",
            trade_date=date(previous_year, 7, 1),
            symbol="AAA",
            quantity=-1,
            gross_amount=150,
            funding_group=group.name,
            cash_currency=Currency.JPY,
            market=Market.JP,
            taxed=TaxStatus.NO,
            memo=None,
        ),
        Transaction(
            id="buy-current",
            trade_date=date(current_year, 3, 1),
            symbol="AAA",
            quantity=1,
            gross_amount=200,
            funding_group=group.name,
            cash_currency=Currency.JPY,
            market=Market.JP,
            taxed=TaxStatus.YES,
            memo=None,
        ),
        Transaction(
            id="sell-current",
            trade_date=date(current_year, 9, 1),
            symbol="AAA",
            quantity=-1,
            gross_amount=250,
            funding_group=group.name,
            cash_currency=Currency.JPY,
            market=Market.JP,
            taxed=TaxStatus.NO,
            memo=None,
        ),
    ]

    snapshot = compute_fund_snapshots(transactions, [group]).funds[0]
    assert snapshot.total_pl == pytest.approx(100)
    assert snapshot.previous_year_pl == pytest.approx(50)
    assert snapshot.previous_year_pl_ratio == pytest.approx(0.05)
    expected_current_ratio = 50 / 1050
    assert snapshot.current_year_pl == pytest.approx(50)
    assert snapshot.current_year_pl_ratio == pytest.approx(expected_current_ratio)


def test_tax_settlement_update_and_delete(client: TestClient):
    buy_payload = {
        "trade_date": "2025-09-01",
        "symbol": "6758.T",
        "quantity": 20,
        "gross_amount": 200000,
        "funding_group": "Default JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }
    sell_payload = {
        "trade_date": "2025-09-20",
        "symbol": "6758.T",
        "quantity": -10,
        "gross_amount": 130000,
        "funding_group": "Default JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }

    buy_resp = client.post("/api/transactions", json=buy_payload)
    assert buy_resp.status_code == 201

    sell_resp = client.post("/api/transactions", json=sell_payload)
    assert sell_resp.status_code == 201
    sell_id = sell_resp.json()["id"]

    tax_payload = {
        "transaction_id": sell_id,
        "funding_group": "Default JPY",
        "amount": 1500,
        "currency": "JPY",
    }
    tax_resp = client.post("/api/tax/settlements", json=tax_payload)
    assert tax_resp.status_code == 201
    settlement_id = tax_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/tax/settlements/{settlement_id}",
        json={"amount": 1750},
    )
    assert patch_resp.status_code == 200
    patch_body = patch_resp.json()
    assert patch_body["amount"] == 1750
    assert patch_body["jpy_equivalent"] == pytest.approx(1750)

    invalid_group = client.patch(
        f"/api/tax/settlements/{settlement_id}",
        json={"funding_group": "Default USD"},
    )
    assert invalid_group.status_code == 400

    delete_resp = client.delete(f"/api/tax/settlements/{settlement_id}")
    assert delete_resp.status_code == 204

    post_delete = client.get("/api/transactions").json()
    target_transaction = next(item for item in post_delete if item["id"] == sell_id)
    assert target_transaction["taxed"] == "N"

    remaining_settlements = client.get("/api/tax/settlements").json()
    assert all(item["id"] != settlement_id for item in remaining_settlements)


def test_usd_tax_settlement_requires_exchange_rate(client: TestClient):
    buy_payload = {
        "trade_date": "2025-09-01",
        "symbol": "AAPL",
        "quantity": 10,
        "gross_amount": 15000,
        "funding_group": "Default USD",
        "cash_currency": "USD",
        "market": "US",
    }
    sell_payload = {
        "trade_date": "2025-09-10",
        "symbol": "AAPL",
        "quantity": -5,
        "gross_amount": 8200,
        "funding_group": "Default USD",
        "cash_currency": "USD",
        "market": "US",
    }

    assert client.post("/api/transactions", json=buy_payload).status_code == 201
    sell_resp = client.post("/api/transactions", json=sell_payload)
    assert sell_resp.status_code == 201, sell_resp.text
    sale_id = sell_resp.json()["id"]

    missing_rate_payload = {
        "transaction_id": sale_id,
        "funding_group": "Default USD",
        "amount": 120,
        "currency": "USD",
    }
    missing_rate_resp = client.post("/api/tax/settlements", json=missing_rate_payload)
    assert missing_rate_resp.status_code == 422

    tax_payload = {
        "transaction_id": sale_id,
        "funding_group": "Default USD",
        "amount": 120,
        "currency": "USD",
        "exchange_rate": 147.85,
    }
    tax_resp = client.post("/api/tax/settlements", json=tax_payload)
    assert tax_resp.status_code == 201, tax_resp.text
    body = tax_resp.json()
    assert body["currency"] == "USD"
    assert body["amount"] == pytest.approx(120)
    assert body["exchange_rate"] == pytest.approx(147.85)
    assert body["jpy_equivalent"] == pytest.approx(17742.0)

    settlement_id = body["id"]

    update_resp = client.patch(
        f"/api/tax/settlements/{settlement_id}",
        json={"amount": 150, "exchange_rate": 149.1},
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["amount"] == pytest.approx(150)
    assert updated["exchange_rate"] == pytest.approx(149.1)
    assert updated["jpy_equivalent"] == pytest.approx(22365.0)

    settlements = client.get("/api/tax/settlements").json()
    record = next(item for item in settlements if item["id"] == settlement_id)
    assert record["currency"] == "USD"
    assert record["funding_group"] == "Default USD"
    assert record["jpy_equivalent"] == pytest.approx(22365.0)