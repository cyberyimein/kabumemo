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

    return TestClient(app)


def test_transaction_lifecycle(client: TestClient):
    resp = client.get("/api/funding-groups")
    assert resp.status_code == 200
    groups = resp.json()
    assert any(group["name"] == "Default JPY" for group in groups)

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
    assert positions[0]["quantity"] == 6
    assert positions[0]["realized_pl"] == 20000

    funds_resp = client.get("/api/funds")
    assert funds_resp.status_code == 200
    funds = {item["name"]: item for item in funds_resp.json()}
    default_fund = funds["Default JPY"]
    assert default_fund["cash_balance"] == -70000
    assert default_fund["holding_cost"] == 90000
    assert default_fund["current_total"] == 20000
    assert default_fund["total_pl"] == 20000

    tax_payload = {
        "transaction_id": sale_id,
        "funding_group": "Default JPY",
        "amount": 1000,
        "currency": "JPY",
    }
    tax_resp = client.post("/api/tax/settlements", json=tax_payload)
    assert tax_resp.status_code == 200, tax_resp.text
    assert tax_resp.json()["new_tax_status"] == "Y"

    revert_after_settlement = client.put(
        f"/api/transactions/{sale_id}",
        json=update_payload,
    )
    assert revert_after_settlement.status_code == 400
    assert "untaxed" in revert_after_settlement.text

    funds_after_tax = client.get("/api/funds").json()
    funds_map = {item["name"]: item for item in funds_after_tax}
    after_tax_default = funds_map["Default JPY"]
    assert after_tax_default["cash_balance"] == -71000
    assert after_tax_default["holding_cost"] == 90000
    assert after_tax_default["current_total"] == 19000
    assert after_tax_default["total_pl"] == 19000

    second_tax = client.post("/api/tax/settlements", json=tax_payload)
    assert second_tax.status_code == 400

    delete_resp = client.delete(f"/api/transactions/{sale_id}")
    assert delete_resp.status_code == 204

    remaining_transactions = client.get("/api/transactions").json()
    assert all(tx["id"] != sale_id for tx in remaining_transactions)

    positions_after_delete = client.get("/api/positions").json()
    assert positions_after_delete[0]["quantity"] == 10
    assert positions_after_delete[0]["realized_pl"] == 0

    delete_again = client.delete(f"/api/transactions/{sale_id}")
    assert delete_again.status_code == 404


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
    assert position.quantity == 0
    assert position.realized_pl == 10000


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

    snapshots = compute_fund_snapshots([buy, sell], [group])
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.holding_cost == 0
    assert snapshot.cash_balance == 20
    assert snapshot.current_total == 20