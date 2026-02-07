from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.storage.repository import LocalDataRepository


def resolve_data_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_path = os.environ.get("KABUCOUNT_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import existing JSON data into the Kabumemo SQLite mirror."
    )
    parser.add_argument(
        "--data-dir",
        help="Directory containing the JSON files and where the SQLite database should live.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing SQLite content even if tables already contain data.",
    )
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    repository = LocalDataRepository(base_path=data_dir)

    if repository.sqlite_has_data() and not args.force:
        db_path = repository.sqlite.db_path
        raise SystemExit(
            f"SQLite database at {db_path} already contains data. "
            "Re-run with --force to overwrite the existing contents."
        )

    repository.sync_sqlite_from_json()

    transactions = len(repository.list_transactions_from_sqlite())
    groups = len(repository.list_funding_groups_from_sqlite())
    settlements = len(repository.list_tax_settlements_from_sqlite())
    exchanges = len(repository.list_fx_exchanges_from_sqlite())
    quotes = len(repository.list_quotes_from_sqlite())

    print(
        "Imported data into SQLite database at",
        repository.sqlite.db_path,
    )
    print(
        "Transactions:",
        transactions,
        "Funding groups:",
        groups,
        "Tax settlements:",
        settlements,
        "FX exchanges:",
        exchanges,
        "Quotes:",
        quotes,
    )


if __name__ == "__main__":
    main()
