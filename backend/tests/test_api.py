from __future__ import annotations

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


def test_transaction_lifecycle(client: TestClient, monkeypatch):
    from datetime import date as real_date

    import app.services.analytics as analytics

    class FixedDate(real_date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return cls(2025, 12, 15)

    monkeypatch.setattr(analytics, "date", FixedDate)

    repository = getattr(client, "repository")

    resp = client.get("/api/funding-groups")
    assert resp.status_code == 200
    groups = resp.json()
    assert any(group["name"] == "JPY" for group in groups)

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
        "funding_group": "JPY",
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
        "funding_group": "JPY",
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
        "funding_group": "JPY",
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
    assert any(entry["funding_group"] == "JPY" for entry in group_breakdown)
    default_group_entry = next(
        entry for entry in group_breakdown if entry["funding_group"] == "JPY"
    )
    assert default_group_entry["currency"] == "JPY"
    assert default_group_entry["quantity"] == 6
    assert default_group_entry["average_cost"] == pytest.approx(15000)
    assert default_group_entry["realized_pl"] == pytest.approx(20000)

    funds_resp = client.get("/api/funds")
    assert funds_resp.status_code == 200
    payload = funds_resp.json()
    funds = {item["name"]: item for item in payload["funds"]}
    default_fund = funds["JPY"]
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
        "funding_group": "JPY",
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
    after_tax_default = funds_map["JPY"]
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
    assert post_delete_group[0]["funding_group"] == "JPY"
    assert post_delete_group[0]["quantity"] == 10
    assert post_delete_group[0]["realized_pl"] == 0

    delete_again = client.delete(f"/api/transactions/{sale_id}")
    assert delete_again.status_code == 404


def test_realized_pnl_is_generated_and_updated(client: TestClient):
    buy_payload = {
        "trade_date": "2025-09-01",
        "symbol": "7203.T",
        "quantity": 10,
        "gross_amount": 150000,
        "funding_group": "JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }
    sell_payload = {
        "trade_date": "2025-09-15",
        "symbol": "7203.T",
        "quantity": -4,
        "gross_amount": 80000,
        "funding_group": "JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }

    assert client.post("/api/transactions", json=buy_payload).status_code == 201
    sell_resp = client.post("/api/transactions", json=sell_payload)
    assert sell_resp.status_code == 201, sell_resp.text
    sell_id = sell_resp.json()["id"]

    realized_resp = client.get("/api/realized-pnl")
    assert realized_resp.status_code == 200, realized_resp.text
    realized_records = realized_resp.json()
    assert len(realized_records) == 1
    assert realized_records[0]["sell_transaction_id"] == sell_id
    assert realized_records[0]["realized_pl"] == pytest.approx(20000)
    assert realized_records[0]["cost_basis"] == pytest.approx(60000)
    assert realized_records[0]["proceeds_amount"] == pytest.approx(80000)
    assert realized_records[0]["allocations"][0]["funding_group"] == "JPY"

    update_payload = {
        **sell_payload,
        "quantity": -5,
        "gross_amount": 90000,
        "taxed": "N",
    }
    update_resp = client.put(f"/api/transactions/{sell_id}", json=update_payload)
    assert update_resp.status_code == 200, update_resp.text

    updated_realized = client.get("/api/realized-pnl").json()
    assert len(updated_realized) == 1
    assert updated_realized[0]["sell_transaction_id"] == sell_id
    assert updated_realized[0]["realized_pl"] == pytest.approx(15000)
    assert updated_realized[0]["cost_basis"] == pytest.approx(75000)
    assert updated_realized[0]["proceeds_amount"] == pytest.approx(90000)


def test_transaction_supports_distinct_position_and_settlement_groups(client: TestClient):
    buy_payload = {
        "trade_date": "2024-07-18",
        "symbol": "NVDA",
        "quantity": 1,
        "gross_amount": 18000,
        "funding_group": "JPY",
        "position_group": "JPY",
        "settlement_group": "JPY",
        "cash_currency": "JPY",
        "trade_currency": "USD",
        "trade_amount": 119.30,
        "settlement_currency": "JPY",
        "settlement_amount": 18000,
        "market": "US",
        "broker_account_type": "SPECIFIC",
    }
    sell_payload = {
        "trade_date": "2024-07-18",
        "symbol": "NVDA",
        "quantity": -1,
        "gross_amount": 118.14,
        "funding_group": "JPY",
        "position_group": "JPY",
        "settlement_group": "USD",
        "cash_currency": "USD",
        "trade_currency": "USD",
        "trade_amount": 118.72,
        "settlement_currency": "USD",
        "settlement_amount": 118.14,
        "market": "US",
        "broker_account_type": "SPECIFIC",
        "taxed": "N",
    }

    assert client.post("/api/transactions", json=buy_payload).status_code == 201
    sell_resp = client.post("/api/transactions", json=sell_payload)
    assert sell_resp.status_code == 201, sell_resp.text

    created = sell_resp.json()
    assert created["position_group"] == "JPY"
    assert created["settlement_group"] == "USD"
    assert created["cash_currency"] == "USD"
    assert created["trade_currency"] == "USD"
    assert created["trade_amount"] == pytest.approx(118.72)
    assert created["settlement_currency"] == "USD"
    assert created["settlement_amount"] == pytest.approx(118.14)


def test_broker_import_rebuilds_realized_pnl(client: TestClient):
    import base64

    domestic_csv = """
約定履歴照会

約定日,銘柄,銘柄コード,市場,取引,期限,預り,課税,約定数量,約定単価,手数料/諸経費等,税額,受渡日,受渡金額/決済損益
2025/07/15,ＮＴＴ,9432,東証,株式現物買,--, 特定 ,--,500,150.2,--,--,2025/07/17,75100
2025/07/24,ＮＴＴ,9432,東証,株式現物売,--, 特定 ,申告,500,152.7,--,--,2025/07/28,76350
""".strip()
    us_csv = """
約定履歴

国内約定日,銘柄,銘柄コード,市場,商品区分,注文種別,取引,預り区分,約定数量,約定単価,国内受渡日,受渡金額/決済損益
2025/08/28,シャオペン ADR,XPEV,NYSE,米国株式,指値,現買,NISA,10,22.6550USD,2025/09/01,226.55USD
""".strip()

    payload = {
        "domestic_report": {
            "file_name": "domestic.csv",
            "content_base64": base64.b64encode(domestic_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        },
        "us_report": {
            "file_name": "us.csv",
            "content_base64": base64.b64encode(us_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        },
        "replace_existing_transactions": True,
    }

    apply_resp = client.post("/api/imports/broker/apply", json=payload)
    assert apply_resp.status_code == 200, apply_resp.text
    assert apply_resp.json()["applied_count"] == 3

    realized_resp = client.get("/api/realized-pnl")
    assert realized_resp.status_code == 200, realized_resp.text
    realized_records = realized_resp.json()
    assert len(realized_records) == 1
    assert realized_records[0]["symbol"] == "9432.T"
    assert realized_records[0]["realized_pl"] == pytest.approx(1250)


def test_cash_report_import_links_jpy_and_foreign_transfer_and_skips_duplicates(
    client: TestClient,
):
    import base64

    jpy_csv = """
円貨入出金明細

入出金日,取引,区分,摘要,出金額,入金額
2026/07/10,出金,その他,米国株式買付代金,78423,0
2026/07/09,出金,その他,譲渡益税源泉徴収金,442,0
2026/07/08,入金,金融機関からの入金,即時入金　三井住友銀行,0,100000
""".strip()
    foreign_csv = """
外貨入出金明細

入出金日,取引,区分,通貨,摘要,出金額,入金額
2026/07/10,入金,-,-,入出金振替,0,78423.00
2026/07/01,入金,配当金,米ドル,NVDA 銘柄名:エヌビディア,0,1.13
""".strip()

    payload = {
        "jpy_cash_report": {
            "file_name": "jpy-cash.csv",
            "content_base64": base64.b64encode(jpy_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        },
        "foreign_cash_report": {
            "file_name": "foreign-cash.csv",
            "content_base64": base64.b64encode(foreign_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        },
    }

    preview = client.post("/api/imports/broker/preview", json=payload)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert len(body["cash_items"]) == 5
    assert body["applied_cash_count"] == 5
    linked = [item for item in body["cash_items"] if item["link_group_id"]]
    assert len(linked) == 2
    assert linked[0]["linked_activity_id"] == linked[1]["id"]
    assert linked[1]["linked_activity_id"] == linked[0]["id"]
    foreign_transfer = next(item for item in linked if item["description"] == "入出金振替")
    assert foreign_transfer["currency"] is None
    tax = next(item for item in body["cash_items"] if "税" in item["description"])
    assert tax["category"] == "tax"

    first = client.post("/api/imports/broker/apply", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["applied_cash_count"] == 5
    second = client.post("/api/imports/broker/apply", json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["applied_cash_count"] == 0
    assert second.json()["skipped_cash_count"] == 5

    ledger = client.get("/api/cash-activities")
    assert ledger.status_code == 200
    assert len(ledger.json()) == 5

    funds = client.get("/api/funds")
    assert funds.status_code == 200, funds.text
    by_currency = {item["currency"]: item for item in funds.json()["aggregated"]}
    assert by_currency["JPY"]["initial_amount"] == pytest.approx(100000)
    assert by_currency["JPY"]["cash_balance"] == pytest.approx(99558)
    assert by_currency["JPY"]["total_pl"] == pytest.approx(-442)
    assert by_currency["USD"]["cash_balance"] == pytest.approx(1.13)
    assert by_currency["USD"]["total_pl"] == pytest.approx(1.13)


def test_cash_only_replace_preserves_transactions_and_other_cash_currency(client: TestClient):
    import base64

    transaction = client.post(
        "/api/transactions",
        json={
            "trade_date": "2026-07-01",
            "symbol": "7203.T",
            "quantity": 1,
            "gross_amount": 2500,
            "funding_group": "JPY",
            "cash_currency": "JPY",
            "market": "JP",
        },
    )
    assert transaction.status_code == 201

    foreign_csv = """
外貨入出金明細

入出金日,取引,区分,通貨,摘要,出金額,入金額
2026/07/01,入金,配当金,米ドル,NVDA 配当,0,1.13
""".strip()
    jpy_csv = """
円貨入出金明細

入出金日,取引,区分,摘要,出金額,入金額
2026/07/08,入金,金融機関からの入金,即時入金,0,100000
""".strip()
    encode = lambda value: base64.b64encode(value.encode("utf-8")).decode("ascii")

    first = client.post(
        "/api/imports/broker/apply",
        json={
            "foreign_cash_report": {
                "file_name": "foreign.csv",
                "content_base64": encode(foreign_csv),
                "encoding_hint": "utf-8",
            }
        },
    )
    assert first.status_code == 200, first.text

    replaced = client.post(
        "/api/imports/broker/apply",
        json={
            "jpy_cash_report": {
                "file_name": "jpy.csv",
                "content_base64": encode(jpy_csv),
                "encoding_hint": "utf-8",
            },
            "replace_existing_transactions": True,
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert len(client.get("/api/transactions").json()) == 1
    cash = client.get("/api/cash-activities").json()
    assert len(cash) == 2
    assert {item["currency"] for item in cash} == {"JPY", "USD"}


def test_broker_import_undo_removes_transactions_and_cash_activities(client: TestClient):
    import base64

    domestic_csv = """
約定履歴照会

約定日,銘柄,銘柄コード,市場,取引,期限,預り,課税,約定数量,約定単価,手数料/諸経費等,税額,受渡日,受渡金額/決済損益
2026/07/15,ＮＴＴ,9432,東証,株式現物買,--,特定,--,10,150,--,--,2026/07/17,1500
""".strip()
    jpy_csv = """
円貨入出金明細

入出金日,取引,区分,摘要,出金額,入金額
2026/07/08,入金,金融機関からの入金,即時入金,0,100000
""".strip()
    encode = lambda value: base64.b64encode(value.encode("utf-8")).decode("ascii")
    applied = client.post(
        "/api/imports/broker/apply",
        json={
            "domestic_report": {
                "file_name": "domestic.csv",
                "content_base64": encode(domestic_csv),
                "encoding_hint": "utf-8",
            },
            "jpy_cash_report": {
                "file_name": "jpy.csv",
                "content_base64": encode(jpy_csv),
                "encoding_hint": "utf-8",
            },
        },
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()

    undone = client.post(
        "/api/imports/broker/undo",
        json={
            "transaction_ids": body["applied_transaction_ids"],
            "cash_activity_ids": body["applied_cash_activity_ids"],
        },
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["deleted_transaction_ids"] == body["applied_transaction_ids"]
    assert undone.json()["deleted_cash_activity_ids"] == body["applied_cash_activity_ids"]
    assert client.get("/api/transactions").json() == []
    assert client.get("/api/cash-activities").json() == []


def test_broker_import_preview_respects_distinct_group_mapping(client: TestClient):
    import base64

    us_csv = """
約定履歴

国内約定日,銘柄,銘柄コード,市場,商品区分,注文種別,取引,預り区分,約定数量,約定単価,国内受渡日,受渡金額/決済損益
2024/07/18,エヌビディア,NVDA,NASDAQ,米国株式,指値,現売,特定,1,118.7200USD,2024/07/22,118.14USD
""".strip()

    payload = {
        "us_report": {
            "file_name": "us.csv",
            "content_base64": base64.b64encode(us_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        },
        "position_group_usd": "JPY",
        "settlement_group_usd": "USD",
    }

    preview_resp = client.post("/api/imports/broker/preview", json=payload)
    assert preview_resp.status_code == 200, preview_resp.text
    items = preview_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["position_group"] == "JPY"
    assert items[0]["settlement_group"] == "USD"
    assert items[0]["settlement_currency"] == "USD"
    assert items[0]["trade_currency"] == "USD"


def test_broker_import_same_day_buy_is_sorted_before_sell(client: TestClient):
    import base64

    us_csv = """
約定履歴

国内約定日,銘柄,銘柄コード,市場,商品区分,注文種別,取引,預り区分,約定数量,約定単価,国内受渡日,受渡金額/決済損益
2024/07/18,エヌビディア,NVDA,NASDAQ,米国株式,指値,現売,特定,1,118.7200USD,2024/07/22,118.14USD
2024/07/18,エヌビディア,NVDA,NASDAQ,米国株式,指値,現買,特定,1,118.7200USD,2024/07/22,119.30USD
""".strip()

    payload = {
        "us_report": {
            "file_name": "us.csv",
            "content_base64": base64.b64encode(us_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        },
        "replace_existing_transactions": True,
    }

    apply_resp = client.post("/api/imports/broker/apply", json=payload)
    assert apply_resp.status_code == 200, apply_resp.text

    transactions = client.get("/api/transactions").json()
    assert len(transactions) == 2
    assert transactions[0]["quantity"] == 1
    assert transactions[1]["quantity"] == -1

    realized_records = client.get("/api/realized-pnl").json()
    assert len(realized_records) == 1
    assert realized_records[0]["matched_quantity"] == pytest.approx(1)
    assert realized_records[0]["unmatched_quantity"] == pytest.approx(0)


def test_broker_import_skips_existing_duplicates_even_when_source_file_changes(
    client: TestClient,
):
    import base64

    us_csv = """
約定履歴

国内約定日,銘柄,銘柄コード,市場,商品区分,注文種別,取引,預り区分,約定数量,約定単価,国内受渡日,受渡金額/決済損益
2025/08/28,シャオペン ADR,XPEV,NYSE,米国株式,指値,現買,NISA,10,22.6550USD,2025/09/01,226.55USD
""".strip()

    first_payload = {
        "us_report": {
            "file_name": "us-monthly.csv",
            "content_base64": base64.b64encode(us_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        }
    }
    first_apply = client.post("/api/imports/broker/apply", json=first_payload)
    assert first_apply.status_code == 200, first_apply.text
    first_body = first_apply.json()
    assert first_body["applied_count"] == 1
    assert first_body["skipped_count"] == 0
    assert len(first_body["applied_transaction_ids"]) == 1

    second_payload = {
        "us_report": {
            "file_name": "us-annual.csv",
            "content_base64": base64.b64encode(us_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        }
    }
    second_apply = client.post("/api/imports/broker/apply", json=second_payload)
    assert second_apply.status_code == 200, second_apply.text
    second_body = second_apply.json()
    assert second_body["applied_count"] == 0
    assert second_body["skipped_count"] == 1
    assert second_body["applied_transaction_ids"] == []
    assert "Skipped 1 duplicate transactions" in second_body["warnings"]

    transactions = client.get("/api/transactions").json()
    assert len(transactions) == 1


def test_domestic_broker_import_skips_existing_duplicates_even_when_source_file_changes(
    client: TestClient,
):
    import base64

    domestic_csv = """
約定履歴照会

約定日,銘柄,銘柄コード,市場,取引,期限,預り,課税,約定数量,約定単価,手数料/諸経費等,税額,受渡日,受渡金額/決済損益
2025/07/15,ＮＴＴ,9432,東証,株式現物買,--, 特定 ,--,500,150.2,--,--,2025/07/17,75100
""".strip()

    first_payload = {
        "domestic_report": {
            "file_name": "domestic-july.csv",
            "content_base64": base64.b64encode(domestic_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        }
    }
    first_apply = client.post("/api/imports/broker/apply", json=first_payload)
    assert first_apply.status_code == 200, first_apply.text
    assert first_apply.json()["applied_count"] == 1

    second_payload = {
        "domestic_report": {
            "file_name": "domestic-archive.csv",
            "content_base64": base64.b64encode(domestic_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        }
    }
    second_apply = client.post("/api/imports/broker/apply", json=second_payload)
    assert second_apply.status_code == 200, second_apply.text
    assert second_apply.json()["applied_count"] == 0
    assert second_apply.json()["skipped_count"] == 1

    transactions = client.get("/api/transactions").json()
    assert len(transactions) == 1


def test_broker_import_preview_reports_duplicates_that_would_be_skipped(client: TestClient):
    import base64

    domestic_csv = """
約定履歴照会

約定日,銘柄,銘柄コード,市場,取引,期限,預り,課税,約定数量,約定単価,手数料/諸経費等,税額,受渡日,受渡金額/決済損益
2025/07/15,ＮＴＴ,9432,東証,株式現物買,--, 特定 ,--,500,150.2,--,--,2025/07/17,75100
2025/07/15,ＮＴＴ,9432,東証,株式現物買,--, 特定 ,--,500,150.2,--,--,2025/07/17,75100
""".strip()

    payload = {
        "domestic_report": {
            "file_name": "domestic-duplicate.csv",
            "content_base64": base64.b64encode(domestic_csv.encode("utf-8")).decode("ascii"),
            "encoding_hint": "utf-8",
        }
    }

    preview_resp = client.post("/api/imports/broker/preview", json=payload)
    assert preview_resp.status_code == 200, preview_resp.text
    preview_body = preview_resp.json()
    assert len(preview_body["items"]) == 2
    assert preview_body["applied_count"] == 1
    assert preview_body["skipped_count"] == 1

    apply_resp = client.post("/api/imports/broker/apply", json=payload)
    assert apply_resp.status_code == 200, apply_resp.text
    apply_body = apply_resp.json()
    assert apply_body["applied_count"] == 1
    assert apply_body["skipped_count"] == 1

    transactions = client.get("/api/transactions").json()
    assert len(transactions) == 1


def test_suspicious_duplicate_review_and_batch_delete(client: TestClient):
    payload = {
        "trade_date": "2025-09-01",
        "symbol": "7203.T",
        "quantity": 10,
        "gross_amount": 150000,
        "funding_group": "JPY",
        "cash_currency": "JPY",
        "market": "JP",
        "memo": "duplicate import",
    }

    first_resp = client.post("/api/transactions", json=payload)
    second_resp = client.post("/api/transactions", json=payload)
    assert first_resp.status_code == 201, first_resp.text
    assert second_resp.status_code == 201, second_resp.text

    duplicates_resp = client.get("/api/transactions/suspicious-duplicates")
    assert duplicates_resp.status_code == 200, duplicates_resp.text
    body = duplicates_resp.json()
    assert body["duplicate_transaction_count"] == 2
    assert body["suggested_delete_count"] == 1
    assert len(body["groups"]) == 1
    group = body["groups"][0]
    assert len(group["transactions"]) == 2
    assert len(group["suggested_delete_ids"]) == 1

    delete_resp = client.post(
        "/api/transactions/batch-delete",
        json={"transaction_ids": group["suggested_delete_ids"]},
    )
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["deleted_count"] == 1

    remaining_transactions = client.get("/api/transactions").json()
    assert len(remaining_transactions) == 1

    post_delete_duplicates = client.get("/api/transactions/suspicious-duplicates").json()
    assert post_delete_duplicates["groups"] == []
    assert post_delete_duplicates["duplicate_transaction_count"] == 0
    assert post_delete_duplicates["suggested_delete_count"] == 0


def test_stock_split_endpoint_rebuilds_positions_and_realized_pnl(client: TestClient):
    buy_payload = {
        "trade_date": "2025-12-22",
        "symbol": "8001",
        "quantity": 20,
        "gross_amount": 188320,
        "funding_group": "JPY",
        "cash_currency": "JPY",
        "market": "JP",
        "broker_account_type": "SPECIFIC",
    }
    assert client.post("/api/transactions", json=buy_payload).status_code == 201

    split_payload = {
        "symbol": "8001",
        "market": "JP",
        "effective_date": "2025-12-31",
        "ratio_before": 1,
        "ratio_after": 5,
        "notes": "1 for 5 split",
    }
    split_resp = client.post("/api/stock-splits", json=split_payload)
    assert split_resp.status_code == 201, split_resp.text

    sell_payload = {
        "trade_date": "2026-01-13",
        "symbol": "8001",
        "quantity": -100,
        "gross_amount": 204750,
        "funding_group": "JPY",
        "cash_currency": "JPY",
        "market": "JP",
        "broker_account_type": "SPECIFIC",
    }
    sell_resp = client.post("/api/transactions", json=sell_payload)
    assert sell_resp.status_code == 201, sell_resp.text

    positions_resp = client.get("/api/positions")
    assert positions_resp.status_code == 200, positions_resp.text
    position = positions_resp.json()[0]
    assert position["symbol"] == "8001.T"
    assert position["breakdown"][0]["quantity"] == 0
    assert position["breakdown"][0]["realized_pl"] == pytest.approx(16430)

    realized_resp = client.get("/api/realized-pnl")
    assert realized_resp.status_code == 200, realized_resp.text
    realized_record = realized_resp.json()[0]
    assert realized_record["matched_quantity"] == pytest.approx(100)
    assert realized_record["unmatched_quantity"] == pytest.approx(0)
    assert realized_record["cost_basis"] == pytest.approx(188320)
    assert realized_record["realized_pl"] == pytest.approx(16430)


def test_stock_split_detection_returns_unrecorded_corporate_action(client: TestClient, monkeypatch):
    from datetime import date

    import app.services.split_detection as split_detection

    buy_payload = {
        "trade_date": "2025-01-10",
        "symbol": "8001",
        "quantity": 20,
        "gross_amount": 188320,
        "funding_group": "JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }
    assert client.post("/api/transactions", json=buy_payload).status_code == 201

    monkeypatch.setattr(
        split_detection,
        "_fetch_split_events",
        lambda symbol, start: [(date(2025, 12, 31), 5.0)],
    )
    response = client.post("/api/stock-splits/detect")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scanned_symbols"] == 1
    assert body["failed_symbols"] == []
    assert len(body["candidates"]) == 1
    candidate = body["candidates"][0]
    assert candidate["symbol"] == "8001.T"
    assert candidate["ratio_after"] == 5
    assert candidate["quantity_before"] == 20
    assert candidate["suggested_quantity_after"] == 100

    assert client.post(
        "/api/stock-splits",
        json={
            "symbol": "8001",
            "market": "JP",
            "effective_date": "2025-12-31",
            "ratio_before": 1,
            "ratio_after": 5,
        },
    ).status_code == 201
    second_response = client.post("/api/stock-splits/detect")
    assert second_response.status_code == 200
    assert second_response.json()["candidates"] == []


def test_realized_pnl_rebuild_applies_stock_split_before_sell():
    from datetime import date

    from app.models.schemas import (  # type: ignore
        BrokerAccountType,
        Currency,
        Market,
        StockSplitRecord,
        TaxStatus,
        Transaction,
    )
    from app.services.realized_pnl import rebuild_realized_pnl_records  # type: ignore

    buy = Transaction(
        id="nvda-buy",
        trade_date=date(2024, 6, 6),
        symbol="NVDA",
        quantity=1,
        gross_amount=120,
        funding_group="USD",
        cash_currency=Currency.USD,
        broker_account_type=BrokerAccountType.NISA,
        market=Market.US,
        taxed=TaxStatus.YES,
        memo=None,
    )
    sell = Transaction(
        id="nvda-sell",
        trade_date=date(2024, 7, 18),
        symbol="NVDA",
        quantity=-10,
        gross_amount=1180,
        funding_group="USD",
        cash_currency=Currency.USD,
        broker_account_type=BrokerAccountType.NISA,
        market=Market.US,
        taxed=TaxStatus.NO,
        memo=None,
    )
    split = StockSplitRecord(
        id="nvda-split",
        symbol="NVDA",
        market=Market.US,
        effective_date=date(2024, 6, 10),
        ratio_before=1,
        ratio_after=10,
        notes=None,
    )

    records = rebuild_realized_pnl_records([buy, sell], stock_splits=[split])

    assert len(records) == 1
    assert records[0].matched_quantity == pytest.approx(10)
    assert records[0].unmatched_quantity == pytest.approx(0)
    assert records[0].cost_basis == pytest.approx(120)
    assert records[0].realized_pl == pytest.approx(1060)


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
    resp_future = client.post("/api/funding-groups/JPY/capital", json=future_payload)
    assert resp_future.status_code == 201, resp_future.text

    funds_future = client.get("/api/funds").json()
    future_default = next(item for item in funds_future["funds"] if item["name"] == "JPY")
    assert future_default["initial_amount"] == 0
    assert future_default["cash_balance"] == 0
    assert future_default["current_year_pl"] == 0

    current_payload = {
        "amount": 100000,
        "effective_date": "2025-06-01",
        "notes": "mid-year contribution",
    }
    resp_current = client.post("/api/funding-groups/JPY/capital", json=current_payload)
    assert resp_current.status_code == 201, resp_current.text

    funds_current = client.get("/api/funds").json()
    current_default = next(item for item in funds_current["funds"] if item["name"] == "JPY")
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
        funding_group="JPY",
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
        funding_group="JPY",
        cash_currency=Currency.JPY,
        market=Market.JP,
        taxed=TaxStatus.NO,
        memo=None,
    )

    positions = compute_positions([buy, sell])
    assert len(positions) == 1
    position = positions[0]
    assert position.symbol == "8306.T"
    assert len(position.breakdown) == 1
    component = position.breakdown[0]
    assert component.currency.value == "JPY"
    assert component.quantity == 0
    assert component.realized_pl == 10000
    assert len(position.group_breakdown) == 1
    group_entry = position.group_breakdown[0]
    assert group_entry.funding_group == "JPY"
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


def test_positions_sell_consumes_across_funding_groups():
    from datetime import date

    from app.models.schemas import Currency, Market, TaxStatus, Transaction
    from app.services.analytics import compute_positions

    usd_buy = Transaction(
        id="ptir-usd-buy",
        trade_date=date(2025, 11, 13),
        symbol="PTIR",
        quantity=60,
        gross_amount=1839.66,
        funding_group="USD",
        cash_currency=Currency.USD,
        position_group="USD",
        settlement_group="USD",
        trade_currency=Currency.USD,
        trade_amount=1830.6,
        settlement_currency=Currency.USD,
        settlement_amount=1839.66,
        market=Market.US,
        taxed=TaxStatus.YES,
        memo=None,
    )
    jpy_buy = Transaction(
        id="ptir-jpy-buy",
        trade_date=date(2025, 11, 14),
        symbol="PTIR",
        quantity=140,
        gross_amount=590852,
        funding_group="JPY",
        cash_currency=Currency.JPY,
        position_group="JPY",
        settlement_group="JPY",
        trade_currency=Currency.USD,
        trade_amount=3795.4,
        settlement_currency=Currency.JPY,
        settlement_amount=590852,
        market=Market.US,
        taxed=TaxStatus.YES,
        memo=None,
    )
    sell = Transaction(
        id="ptir-sell",
        trade_date=date(2025, 12, 11),
        symbol="PTIR",
        quantity=-200,
        gross_amount=6262,
        funding_group="USD",
        cash_currency=Currency.USD,
        position_group="USD",
        settlement_group="USD",
        trade_currency=Currency.USD,
        trade_amount=6284,
        settlement_currency=Currency.USD,
        settlement_amount=6262,
        market=Market.US,
        taxed=TaxStatus.NO,
        memo=None,
    )

    positions = compute_positions([usd_buy, jpy_buy, sell])

    assert len(positions) == 1
    position = positions[0]
    assert position.symbol == "PTIR"
    assert len(position.breakdown) == 1
    assert position.breakdown[0].currency == Currency.USD
    assert position.breakdown[0].quantity == 0
    assert all(entry.quantity == 0 for entry in position.group_breakdown)


def test_positions_sell_keeps_accounts_separate():
    from datetime import date

    from app.models.schemas import BrokerAccountType, Currency, Market, TaxStatus, Transaction
    from app.services.analytics import compute_positions

    nisa_buy = Transaction(
        id="nisa-buy",
        trade_date=date(2025, 1, 10),
        symbol="TEST",
        quantity=100,
        gross_amount=10000,
        funding_group="JPY",
        cash_currency=Currency.JPY,
        broker_account_type=BrokerAccountType.NISA,
        market=Market.JP,
        taxed=TaxStatus.YES,
        memo=None,
    )
    specific_buy = Transaction(
        id="specific-buy",
        trade_date=date(2025, 1, 11),
        symbol="TEST",
        quantity=100,
        gross_amount=20000,
        funding_group="JPY",
        cash_currency=Currency.JPY,
        broker_account_type=BrokerAccountType.SPECIFIC,
        market=Market.JP,
        taxed=TaxStatus.YES,
        memo=None,
    )
    specific_sell = Transaction(
        id="specific-sell",
        trade_date=date(2025, 1, 12),
        symbol="TEST",
        quantity=-100,
        gross_amount=25000,
        funding_group="JPY",
        cash_currency=Currency.JPY,
        broker_account_type=BrokerAccountType.SPECIFIC,
        market=Market.JP,
        taxed=TaxStatus.NO,
        memo=None,
    )

    positions = compute_positions([nisa_buy, specific_buy, specific_sell])

    assert len(positions) == 1
    position = positions[0]
    assert position.symbol == "TEST.T"
    assert len(position.breakdown) == 1
    assert position.breakdown[0].quantity == 100
    assert position.breakdown[0].average_cost == 100
    assert position.breakdown[0].realized_pl == 5000

    group_entry = next(item for item in position.group_breakdown if item.funding_group == "JPY")
    assert group_entry.quantity == 100
    assert group_entry.average_cost == 100
    assert group_entry.realized_pl == 5000


def test_fund_snapshot_sell_consumes_across_funding_groups():
    from datetime import date

    from app.models.schemas import Currency, FundingGroup, Market, TaxStatus, Transaction
    from app.services.analytics import compute_fund_snapshots

    groups = [
        FundingGroup(name="JPY", currency=Currency.JPY, initial_amount=0),
        FundingGroup(name="USD", currency=Currency.USD, initial_amount=0),
    ]
    transactions = [
        Transaction(
            id="ptir-usd-buy",
            trade_date=date(2025, 11, 13),
            symbol="PTIR",
            quantity=60,
            gross_amount=1839.66,
            funding_group="USD",
            cash_currency=Currency.USD,
            position_group="USD",
            settlement_group="USD",
            trade_currency=Currency.USD,
            trade_amount=1830.6,
            settlement_currency=Currency.USD,
            settlement_amount=1839.66,
            market=Market.US,
            taxed=TaxStatus.YES,
            memo=None,
        ),
        Transaction(
            id="ptir-jpy-buy",
            trade_date=date(2025, 11, 14),
            symbol="PTIR",
            quantity=140,
            gross_amount=590852,
            funding_group="JPY",
            cash_currency=Currency.JPY,
            position_group="JPY",
            settlement_group="JPY",
            trade_currency=Currency.USD,
            trade_amount=3795.4,
            settlement_currency=Currency.JPY,
            settlement_amount=590852,
            market=Market.US,
            taxed=TaxStatus.YES,
            memo=None,
        ),
        Transaction(
            id="ptir-sell",
            trade_date=date(2025, 12, 11),
            symbol="PTIR",
            quantity=-200,
            gross_amount=6262,
            funding_group="USD",
            cash_currency=Currency.USD,
            position_group="USD",
            settlement_group="USD",
            trade_currency=Currency.USD,
            trade_amount=6284,
            settlement_currency=Currency.USD,
            settlement_amount=6262,
            market=Market.US,
            taxed=TaxStatus.NO,
            memo=None,
        ),
    ]

    snapshots = compute_fund_snapshots(transactions, groups).funds
    jpy_snapshot = next(item for item in snapshots if item.name == "JPY")
    usd_snapshot = next(item for item in snapshots if item.name == "USD")

    assert jpy_snapshot.holding_cost == 0
    assert usd_snapshot.holding_cost == 0


def test_fund_snapshot_sell_keeps_accounts_separate():
    from datetime import date

    from app.models.schemas import BrokerAccountType, Currency, FundingGroup, Market, TaxStatus, Transaction
    from app.services.analytics import compute_fund_snapshots

    groups = [FundingGroup(name="JPY", currency=Currency.JPY, initial_amount=0)]
    transactions = [
        Transaction(
            id="nisa-buy",
            trade_date=date(2025, 1, 10),
            symbol="TEST",
            quantity=100,
            gross_amount=10000,
            funding_group="JPY",
            cash_currency=Currency.JPY,
            broker_account_type=BrokerAccountType.NISA,
            market=Market.JP,
            taxed=TaxStatus.YES,
            memo=None,
        ),
        Transaction(
            id="specific-buy",
            trade_date=date(2025, 1, 11),
            symbol="TEST",
            quantity=100,
            gross_amount=20000,
            funding_group="JPY",
            cash_currency=Currency.JPY,
            broker_account_type=BrokerAccountType.SPECIFIC,
            market=Market.JP,
            taxed=TaxStatus.YES,
            memo=None,
        ),
        Transaction(
            id="specific-sell",
            trade_date=date(2025, 1, 12),
            symbol="TEST",
            quantity=-100,
            gross_amount=25000,
            funding_group="JPY",
            cash_currency=Currency.JPY,
            broker_account_type=BrokerAccountType.SPECIFIC,
            market=Market.JP,
            taxed=TaxStatus.NO,
            memo=None,
        ),
    ]

    snapshot = compute_fund_snapshots(transactions, groups).funds[0]
    assert snapshot.cash_balance == -5000
    assert snapshot.holding_cost == 10000
    assert snapshot.current_total == 5000
    assert snapshot.total_pl == 5000


def test_fund_snapshot_includes_standalone_fx_exchange():
    from datetime import date

    from app.models.schemas import Currency, FundingGroup, FxExchangeRecord
    from app.services.analytics import compute_fund_snapshots

    groups = [
        FundingGroup(name="JPY", currency=Currency.JPY, initial_amount=100000),
        FundingGroup(name="USD", currency=Currency.USD, initial_amount=0),
    ]
    fx_exchanges = [
        FxExchangeRecord(
            id="fx-1",
            exchange_date=date(2025, 12, 1),
            from_currency=Currency.JPY,
            to_currency=Currency.USD,
            from_amount=15000,
            to_amount=100,
            rate=150,
            notes=None,
            transaction_id=None,
        )
    ]

    snapshots = compute_fund_snapshots([], groups, fx_exchanges=fx_exchanges).funds
    jpy_snapshot = next(item for item in snapshots if item.name == "JPY")
    usd_snapshot = next(item for item in snapshots if item.name == "USD")

    assert jpy_snapshot.cash_balance == 85000
    assert usd_snapshot.cash_balance == 100
    assert jpy_snapshot.current_total == 85000
    assert usd_snapshot.current_total == 100
    assert jpy_snapshot.total_pl == -15000
    assert usd_snapshot.total_pl == 100
    assert jpy_snapshot.current_year_pl == 0
    assert usd_snapshot.current_year_pl == 0
    assert jpy_snapshot.previous_year_pl == -15000
    assert usd_snapshot.previous_year_pl == 100

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


def test_fund_snapshot_annual_tax_uses_tax_year(monkeypatch):
    from datetime import date as real_date

    import app.services.analytics as analytics
    from app.models.schemas import AnnualTaxSettlement, Currency, FundingGroup
    from app.services.analytics import compute_fund_snapshots

    class FixedDate(real_date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return cls(2026, 3, 9)

    monkeypatch.setattr(analytics, "date", FixedDate)

    group = FundingGroup(name="JPY", currency=Currency.JPY, initial_amount=1000)
    annual_settlements = [
        AnnualTaxSettlement(
            id="annual-2025",
            year=2025,
            funding_group="JPY",
            amount=100,
            currency=Currency.JPY,
            notes=None,
            recorded_at=FixedDate(2026, 3, 9),
        )
    ]

    snapshot = compute_fund_snapshots(
        [],
        [group],
        annual_tax_settlements=annual_settlements,
    ).funds[0]

    assert snapshot.total_pl == pytest.approx(-100)
    assert snapshot.current_year_pl == pytest.approx(0)
    assert snapshot.previous_year_pl == pytest.approx(-100)


def test_fund_snapshot_prefers_realized_pnl_ledger_for_yearly_pl(monkeypatch):
    from datetime import date as real_date

    import app.services.analytics as analytics
    from app.models.schemas import (
        AnnualTaxSettlement,
        BrokerAccountType,
        Currency,
        FundingGroup,
        Market,
        RealizedPnLAllocation,
        RealizedPnLRecord,
    )
    from app.services.analytics import compute_fund_snapshots

    class FixedDate(real_date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return cls(2026, 3, 9)

    monkeypatch.setattr(analytics, "date", FixedDate)

    groups = [
        FundingGroup(name="JPY", currency=Currency.JPY, initial_amount=1000),
        FundingGroup(name="USD", currency=Currency.USD, initial_amount=1000),
    ]
    realized_records = [
        RealizedPnLRecord(
            id="r-jpy-current",
            sell_transaction_id="sell-jpy-current",
            trade_date=FixedDate(2026, 1, 13),
            symbol="8001.T",
            market=Market.JP,
            broker_account_type=BrokerAccountType.SPECIFIC,
            position_currency=Currency.JPY,
            settlement_currency=Currency.JPY,
            quantity=100,
            matched_quantity=100,
            unmatched_quantity=0,
            proceeds_amount=204750,
            cost_basis=188320,
            realized_pl=16430,
            allocations=[
                RealizedPnLAllocation(
                    funding_group="JPY",
                    quantity=100,
                    cost_basis=188320,
                    realized_pl=16430,
                )
            ],
            memo=None,
        ),
        RealizedPnLRecord(
            id="r-usd-previous",
            sell_transaction_id="sell-usd-previous",
            trade_date=FixedDate(2025, 8, 14),
            symbol="AMD",
            market=Market.US,
            broker_account_type=BrokerAccountType.SPECIFIC,
            position_currency=Currency.USD,
            settlement_currency=Currency.USD,
            quantity=7,
            matched_quantity=7,
            unmatched_quantity=0,
            proceeds_amount=1266.1,
            cost_basis=1000,
            realized_pl=266.1,
            allocations=[
                RealizedPnLAllocation(
                    funding_group="USD",
                    quantity=7,
                    cost_basis=1000,
                    realized_pl=266.1,
                )
            ],
            memo=None,
        ),
    ]
    annual_settlements = [
        AnnualTaxSettlement(
            id="annual-2025",
            year=2025,
            funding_group="USD",
            amount=66.1,
            currency=Currency.JPY,
            notes=None,
            recorded_at=FixedDate(2026, 3, 9),
        )
    ]

    snapshots = compute_fund_snapshots(
        [],
        groups,
        annual_tax_settlements=annual_settlements,
        realized_pnl_records=realized_records,
    ).funds

    jpy_snapshot = next(item for item in snapshots if item.name == "JPY")
    usd_snapshot = next(item for item in snapshots if item.name == "USD")

    assert jpy_snapshot.current_year_pl == pytest.approx(16430)
    assert jpy_snapshot.previous_year_pl == pytest.approx(0)
    assert usd_snapshot.current_year_pl == pytest.approx(0)
    assert usd_snapshot.previous_year_pl == pytest.approx(200)


def test_tax_settlement_update_and_delete(client: TestClient):
    buy_payload = {
        "trade_date": "2025-09-01",
        "symbol": "6758.T",
        "quantity": 20,
        "gross_amount": 200000,
        "funding_group": "JPY",
        "cash_currency": "JPY",
        "market": "JP",
    }
    sell_payload = {
        "trade_date": "2025-09-20",
        "symbol": "6758.T",
        "quantity": -10,
        "gross_amount": 130000,
        "funding_group": "JPY",
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
        "funding_group": "JPY",
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
        json={"funding_group": "USD"},
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
        "funding_group": "USD",
        "cash_currency": "USD",
        "market": "US",
    }
    sell_payload = {
        "trade_date": "2025-09-10",
        "symbol": "AAPL",
        "quantity": -5,
        "gross_amount": 8200,
        "funding_group": "USD",
        "cash_currency": "USD",
        "market": "US",
    }

    assert client.post("/api/transactions", json=buy_payload).status_code == 201
    sell_resp = client.post("/api/transactions", json=sell_payload)
    assert sell_resp.status_code == 201, sell_resp.text
    sale_id = sell_resp.json()["id"]

    missing_rate_payload = {
        "transaction_id": sale_id,
        "funding_group": "USD",
        "amount": 120,
        "currency": "USD",
    }
    missing_rate_resp = client.post("/api/tax/settlements", json=missing_rate_payload)
    assert missing_rate_resp.status_code == 422

    tax_payload = {
        "transaction_id": sale_id,
        "funding_group": "JPY",
        "amount": 120,
        "currency": "JPY",
        "balance_exchange_rate": 150.0,
    }
    tax_resp = client.post("/api/tax/settlements", json=tax_payload)
    assert tax_resp.status_code == 201, tax_resp.text
    body = tax_resp.json()
    assert body["currency"] == "JPY"
    assert body["amount"] == pytest.approx(120)
    assert body["exchange_rate"] is None
    assert body["jpy_equivalent"] == pytest.approx(120.0)

    settlement_id = body["id"]

    update_resp = client.patch(
        f"/api/tax/settlements/{settlement_id}",
        json={"amount": 150, "exchange_rate": 149.1},
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["amount"] == pytest.approx(150)
    assert updated["exchange_rate"] is None
    assert updated["jpy_equivalent"] == pytest.approx(150.0)

    settlements = client.get("/api/tax/settlements").json()
    record = next(item for item in settlements if item["id"] == settlement_id)
    assert record["currency"] == "JPY"
    assert record["funding_group"] == "JPY"
    assert record["jpy_equivalent"] == pytest.approx(150.0)


def test_fx_exchange_computes_rate_from_amounts(client: TestClient):
    payload = {
        "exchange_date": "2025-09-01",
        "from_currency": "JPY",
        "to_currency": "USD",
        "from_amount": 150000,
        "to_amount": 1000,
    }

    resp = client.post("/api/fx-exchanges", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["from_currency"] == "JPY"
    assert body["to_currency"] == "USD"
    assert body["from_amount"] == pytest.approx(150000)
    assert body["to_amount"] == pytest.approx(1000)
    assert body["rate"] == pytest.approx(150.0)


def test_fx_exchange_computes_to_amount_from_rate(client: TestClient):
    payload = {
        "exchange_date": "2025-09-01",
        "from_currency": "USD",
        "to_currency": "JPY",
        "from_amount": 1000,
        "rate": 150,
    }

    resp = client.post("/api/fx-exchanges", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["from_currency"] == "USD"
    assert body["to_currency"] == "JPY"
    assert body["from_amount"] == pytest.approx(1000)
    assert body["to_amount"] == pytest.approx(150000)
    assert body["rate"] == pytest.approx(150.0)


def test_fx_exchange_requires_to_amount_or_rate(client: TestClient):
    payload = {
        "exchange_date": "2025-09-01",
        "from_currency": "JPY",
        "to_currency": "USD",
        "from_amount": 150000,
    }

    resp = client.post("/api/fx-exchanges", json=payload)
    assert resp.status_code == 422


def test_cross_currency_requires_cash_currency_match_buy_currency(client: TestClient):
    payload = {
        "trade_date": "2025-09-10",
        "symbol": "AAPL",
        "quantity": -1,
        "gross_amount": 1000,
        "funding_group": "USD",
        "cash_currency": "JPY",
        "cross_currency": True,
        "buy_currency": "USD",
        "sell_currency": "JPY",
        "market": "US",
    }

    resp = client.post("/api/transactions", json=payload)
    assert resp.status_code == 422
