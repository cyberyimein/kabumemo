from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from app.storage.repository import LocalDataRepository


def resolve_data_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_path = os.environ.get("KABUCOUNT_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data"


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8") or "[]")


def write_json(path: Path, payload: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy funding-group data into currency-based groups (JPY/USD).",
    )
    parser.add_argument(
        "--data-dir",
        help="Directory containing the legacy JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to write migrated JSON/SQLite data (defaults to --data-dir).",
    )
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    output_dir = resolve_data_dir(args.output_dir) if args.output_dir else data_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    funding_groups = load_json(data_dir / "funding_groups.json")
    transactions = load_json(data_dir / "transactions.json")
    tax_settlements = load_json(data_dir / "tax_settlements.json")
    capital_adjustments = load_json(data_dir / "capital_adjustments.json")
    fx_exchanges = load_json(data_dir / "fx_exchanges.json")

    group_currency_map: dict[str, str] = {
        group.get("name", ""): group.get("currency", "JPY")
        for group in funding_groups
        if group.get("name")
    }

    merged_groups: dict[str, dict[str, Any]] = {}
    merged_sources: dict[str, list[str]] = {}
    for group in funding_groups:
        currency = group.get("currency") or "JPY"
        bucket = merged_groups.setdefault(
            currency,
            {
                "name": currency,
                "currency": currency,
                "initial_amount": 0.0,
                "notes": None,
            },
        )
        bucket["initial_amount"] += float(group.get("initial_amount", 0.0) or 0.0)
        merged_sources.setdefault(currency, []).append(group.get("name", currency))

    for currency, sources in merged_sources.items():
        names = ", ".join(sorted({name for name in sources if name}))
        if names:
            merged_groups[currency]["notes"] = f"Merged from: {names}"

    migrated_groups = list(merged_groups.values())

    for tx in transactions:
        current_group = tx.get("funding_group", "")
        currency = group_currency_map.get(current_group) or tx.get("cash_currency") or "JPY"
        tx["funding_group"] = currency

    for adjustment in capital_adjustments:
        current_group = adjustment.get("funding_group", "")
        currency = group_currency_map.get(current_group) or "JPY"
        adjustment["funding_group"] = currency

    migrated_settlements: list[dict[str, Any]] = []
    for record in tax_settlements:
        currency = record.get("currency") or "JPY"
        exchange_rate = record.get("exchange_rate")
        amount = float(record.get("amount", 0.0) or 0.0)
        jpy_equivalent = record.get("jpy_equivalent")
        if jpy_equivalent is None:
            if currency == "USD" and exchange_rate:
                jpy_equivalent = amount * float(exchange_rate)
            else:
                jpy_equivalent = amount
        balance_rate = record.get("balance_exchange_rate")
        if not balance_rate and currency == "USD" and exchange_rate:
            balance_rate = exchange_rate

        migrated = dict(record)
        migrated["currency"] = "JPY"
        migrated["exchange_rate"] = None
        migrated["amount"] = round(float(jpy_equivalent), 2)
        migrated["jpy_equivalent"] = round(float(jpy_equivalent), 2)
        migrated["funding_group"] = "JPY"
        migrated["balance_exchange_rate"] = float(balance_rate) if balance_rate else None
        if balance_rate:
            migrated["balance_usd_required"] = round(
                migrated["amount"] / float(balance_rate), 4
            )
        else:
            migrated["balance_usd_required"] = None
        migrated_settlements.append(migrated)

    write_json(output_dir / "funding_groups.json", migrated_groups)
    write_json(output_dir / "transactions.json", transactions)
    write_json(output_dir / "tax_settlements.json", migrated_settlements)
    write_json(output_dir / "capital_adjustments.json", capital_adjustments)
    write_json(output_dir / "fx_exchanges.json", fx_exchanges)

    repository = LocalDataRepository(base_path=output_dir)
    repository.sync_sqlite_from_json()

    print("Migration complete.")
    print("Output directory:", output_dir)


if __name__ == "__main__":
    main()
