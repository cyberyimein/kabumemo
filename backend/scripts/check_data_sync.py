from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, Mapping

from pydantic import BaseModel

from app.storage.repository import LocalDataRepository


def resolve_data_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_path = os.environ.get("KABUCOUNT_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data"


def build_index(models: Iterable[BaseModel], key_field: str) -> Mapping[str, dict]:
    index: dict[str, dict] = {}
    for model in models:
        payload = model.model_dump(mode="json")
        identifier = payload[key_field]
        index[identifier] = payload
    return index


def diff_collections(
    *,
    label: str,
    json_items: Iterable[BaseModel],
    sqlite_items: Iterable[BaseModel],
    key_field: str,
) -> dict:
    json_index = build_index(json_items, key_field)
    sqlite_index = build_index(sqlite_items, key_field)

    json_ids = set(json_index)
    sqlite_ids = set(sqlite_index)

    missing_in_sqlite = sorted(json_ids - sqlite_ids)
    missing_in_json = sorted(sqlite_ids - json_ids)

    mismatched = sorted(
        ident
        for ident in json_ids & sqlite_ids
        if json_index[ident] != sqlite_index[ident]
    )

    return {
        "label": label,
        "json_count": len(json_index),
        "sqlite_count": len(sqlite_index),
        "missing_in_sqlite": missing_in_sqlite,
        "missing_in_json": missing_in_json,
        "mismatched": mismatched,
        "clean": not (missing_in_sqlite or missing_in_json or mismatched),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate that JSON files and SQLite mirror contain identical data.",
    )
    parser.add_argument(
        "--data-dir",
        help="Directory containing JSON files and SQLite database.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed mismatched record identifiers.",
    )
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    repository = LocalDataRepository(base_path=data_dir)

    results = [
        diff_collections(
            label="transactions",
            json_items=repository.list_transactions(),
            sqlite_items=repository.list_transactions_from_sqlite(),
            key_field="id",
        ),
        diff_collections(
            label="funding groups",
            json_items=repository.list_funding_groups(),
            sqlite_items=repository.list_funding_groups_from_sqlite(),
            key_field="name",
        ),
        diff_collections(
            label="tax settlements",
            json_items=repository.list_tax_settlements(),
            sqlite_items=repository.list_tax_settlements_from_sqlite(),
            key_field="id",
        ),
        diff_collections(
            label="fx exchanges",
            json_items=repository.list_fx_exchanges(),
            sqlite_items=repository.list_fx_exchanges_from_sqlite(),
            key_field="id",
        ),
        diff_collections(
            label="quotes",
            json_items=repository.list_quotes(),
            sqlite_items=repository.list_quotes_from_sqlite(),
            key_field="symbol",
        ),
    ]

    clean = all(item["clean"] for item in results)

    for item in results:
        status = "OK" if item["clean"] else "DIFF"
        print(
            f"[{status}] {item['label']}: JSON={item['json_count']} SQLite={item['sqlite_count']}"
        )
        if not item["clean"] and args.verbose:
            if item["missing_in_sqlite"]:
                print("  Missing in SQLite:", ", ".join(item["missing_in_sqlite"]))
            if item["missing_in_json"]:
                print("  Missing in JSON:", ", ".join(item["missing_in_json"]))
            if item["mismatched"]:
                print("  Value mismatches:", ", ".join(item["mismatched"]))

    if not clean:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
