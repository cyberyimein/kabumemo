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

    pos_resp = client.get("/api/positions")
    assert pos_resp.status_code == 200
    positions = pos_resp.json()
    assert positions[0]["quantity"] == 5
    assert positions[0]["realized_pl"] == 15000

    funds_resp = client.get("/api/funds")
    assert funds_resp.status_code == 200
    funds = {item["name"]: item for item in funds_resp.json()}
    assert funds["Default JPY"]["current_total"] == -60000

    tax_payload = {
        "transaction_id": sale_id,
        "funding_group": "Default JPY",
        "amount": 1000,
        "currency": "JPY",
    }
    tax_resp = client.post("/api/tax/settlements", json=tax_payload)
    assert tax_resp.status_code == 200, tax_resp.text
    assert tax_resp.json()["new_tax_status"] == "Y"

    funds_after_tax = client.get("/api/funds").json()
    funds_map = {item["name"]: item for item in funds_after_tax}
    assert funds_map["Default JPY"]["current_total"] == -61000

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