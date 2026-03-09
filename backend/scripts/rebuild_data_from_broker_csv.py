from __future__ import annotations

import argparse
import base64
from pathlib import Path

from app.models.schemas import BrokerImportApplyRequest, BrokerImportFile
from app.services.broker_import import apply_broker_import, preview_items_to_transactions
from app.services.realized_pnl import rebuild_and_persist_realized_pnl
from app.storage.repository import LocalDataRepository


def _read_report(path: Path) -> BrokerImportFile:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return BrokerImportFile(
        file_name=path.name,
        content_base64=payload,
        encoding_hint="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild transactions and realized PnL from domestic and US broker CSV reports."
    )
    parser.add_argument(
        "--domestic-report",
        default="realdata/export/SaveFile_000001_000027.utf8.csv",
        help="Domestic broker CSV report path",
    )
    parser.add_argument(
        "--us-report",
        default="realdata/export/PaymentRecords.utf8.csv",
        help="US broker CSV report path",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Target data directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = LocalDataRepository(base_path=Path(args.data_dir).expanduser().resolve())
    repo.ensure_default_groups()

    preview = apply_broker_import(
        BrokerImportApplyRequest(
            domestic_report=_read_report(Path(args.domestic_report).expanduser().resolve()),
            us_report=_read_report(Path(args.us_report).expanduser().resolve()),
            position_group_jpy="JPY",
            settlement_group_jpy="JPY",
            position_group_usd="USD",
            settlement_group_usd="USD",
            replace_existing_transactions=True,
        )
    )
    transactions = preview_items_to_transactions(preview.items)
    repo.replace_transactions(transactions)
    repo.clear_tax_settlements()
    realized_records = rebuild_and_persist_realized_pnl(repo, transactions)
    repo.sync_sqlite_from_json()
    unmatched_records = [item for item in realized_records if item.unmatched_quantity > 1e-9]

    print(f"Imported transactions: {len(transactions)}")
    print(f"Realized PnL records: {len(realized_records)}")
    print(f"Realized PnL records with unmatched quantity: {len(unmatched_records)}")
    print(f"Warnings: {len(preview.warnings)}")
    for warning in preview.warnings:
        print(f"  - {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())