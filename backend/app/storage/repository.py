from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List
from uuid import uuid4

from ..models.schemas import (
    Currency,
    FundingGroup,
    FundingGroupUpdate,
    TaxStatus,
    Transaction,
    TransactionCreate,
)


class LocalDataRepository:
    """Simple JSON-backed repository for local single-user use."""

    def __init__(self, base_path: Path | None = None) -> None:
        env_path = os.environ.get("KABUCOUNT_DATA_DIR")
        base_dir = Path(env_path) if env_path else Path(__file__).resolve().parents[3] / "data"
        self.base_path = base_path or base_dir
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._transactions_path = self.base_path / "transactions.json"
        self._funding_groups_path = self.base_path / "funding_groups.json"
        self._tax_settlements_path = self.base_path / "tax_settlements.json"
        for path in (
            self._transactions_path,
            self._funding_groups_path,
            self._tax_settlements_path,
        ):
            if not path.exists():
                path.write_text("[]", encoding="utf-8")

    # Transactions -----------------------------------------------------------------
    def list_transactions(self) -> List[Transaction]:
        payload = json.loads(self._transactions_path.read_text(encoding="utf-8") or "[]")
        return [Transaction(**item) for item in payload]

    def get_transaction(self, transaction_id: str) -> Transaction:
        for transaction in self.list_transactions():
            if transaction.id == transaction_id:
                return transaction
        raise ValueError(f"Transaction {transaction_id} not found")

    def add_transaction(self, transaction: TransactionCreate) -> Transaction:
        transactions = self.list_transactions()
        new_transaction = Transaction(id=str(uuid4()), **transaction.model_dump())
        transactions.append(new_transaction)
        self._write_transactions(transactions)
        return new_transaction

    def update_transaction(self, updated: Transaction) -> None:
        transactions = self.list_transactions()
        for index, item in enumerate(transactions):
            if item.id == updated.id:
                transactions[index] = updated
                self._write_transactions(transactions)
                return
        raise ValueError(f"Transaction {updated.id} not found")

    def delete_transaction(self, transaction_id: str) -> None:
        transactions = self.list_transactions()
        remaining_transactions = [tx for tx in transactions if tx.id != transaction_id]
        if len(remaining_transactions) == len(transactions):
            raise ValueError(f"Transaction {transaction_id} not found")
        self._write_transactions(remaining_transactions)

        settlements = self.list_tax_settlements()
        filtered_settlements = [item for item in settlements if item.get("transaction_id") != transaction_id]
        if len(filtered_settlements) != len(settlements):
            self._write_tax_settlements(filtered_settlements)

    def _write_transactions(self, transactions: Iterable[Transaction]) -> None:
        serialized = [t.model_dump(mode="json") for t in transactions]
        self._transactions_path.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Funding groups ----------------------------------------------------------------
    def list_funding_groups(self) -> List[FundingGroup]:
        payload = json.loads(self._funding_groups_path.read_text(encoding="utf-8") or "[]")
        return [FundingGroup(**item) for item in payload]

    def get_funding_group(self, name: str) -> FundingGroup:
        for group in self.list_funding_groups():
            if group.name == name:
                return group
        raise ValueError(f"Funding group {name} not found")

    def upsert_funding_group(self, group: FundingGroup) -> FundingGroup:
        groups = self.list_funding_groups()
        remaining = [g for g in groups if g.name != group.name]
        remaining.append(group)
        self._write_funding_groups(remaining)
        return group

    def patch_funding_group(self, name: str, patch: FundingGroupUpdate) -> FundingGroup:
        groups = self.list_funding_groups()
        for index, group in enumerate(groups):
            if group.name == name:
                updated = group.model_copy(update=patch.model_dump(exclude_unset=True))
                groups[index] = updated
                self._write_funding_groups(groups)
                return updated
        raise ValueError(f"Funding group {name} not found")

    def delete_funding_group(self, name: str) -> None:
        groups = self.list_funding_groups()
        filtered = [g for g in groups if g.name != name]
        if len(filtered) == len(groups):
            raise ValueError(f"Funding group {name} not found")
        self._write_funding_groups(filtered)

    def _write_funding_groups(self, groups: Iterable[FundingGroup]) -> None:
        serialized = [g.model_dump(mode="json") for g in groups]
        self._funding_groups_path.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Utility -----------------------------------------------------------------------
    def ensure_default_groups(self) -> None:
        if self.list_funding_groups():
            return
        defaults = [
            FundingGroup(name="Default JPY", currency=Currency.JPY, initial_amount=0.0),
            FundingGroup(name="Default USD", currency=Currency.USD, initial_amount=0.0),
        ]
        self._write_funding_groups(defaults)

    def mark_transaction_taxed(self, transaction_id: str) -> Transaction:
        transactions = self.list_transactions()
        for index, item in enumerate(transactions):
            if item.id == transaction_id:
                updated = item.model_copy(update={"taxed": TaxStatus.YES})
                transactions[index] = updated
                self._write_transactions(transactions)
                return updated
        raise ValueError(f"Transaction {transaction_id} not found")

    # Tax settlements ---------------------------------------------------------------
    def list_tax_settlements(self) -> list[dict[str, object]]:
        payload = json.loads(self._tax_settlements_path.read_text(encoding="utf-8") or "[]")
        return list(payload)

    def add_tax_settlement(self, settlement: dict[str, object]) -> None:
        settlements = self.list_tax_settlements()
        settlements.append(settlement)
        self._write_tax_settlements(settlements)

    def _write_tax_settlements(self, settlements: Iterable[dict[str, object]]) -> None:
        self._tax_settlements_path.write_text(
            json.dumps(list(settlements), ensure_ascii=False, indent=2), encoding="utf-8"
        )
