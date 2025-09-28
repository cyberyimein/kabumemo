from __future__ import annotations

import json
import os
from datetime import date
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
    TaxSettlementRecord,
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

    def update_transaction(self, updated: Transaction) -> Transaction:
        transactions = self.list_transactions()
        for index, item in enumerate(transactions):
            if item.id == updated.id:
                transactions[index] = updated
                self._write_transactions(transactions)
                return updated
        raise ValueError(f"Transaction {updated.id} not found")

    def delete_transaction(self, transaction_id: str) -> None:
        transactions = self.list_transactions()
        remaining_transactions = [tx for tx in transactions if tx.id != transaction_id]
        if len(remaining_transactions) == len(transactions):
            raise ValueError(f"Transaction {transaction_id} not found")
        self._write_transactions(remaining_transactions)

        settlements = self.list_tax_settlements()
        filtered_settlements = [item for item in settlements if item.transaction_id != transaction_id]
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

    def set_transaction_tax_status(self, transaction_id: str, status: TaxStatus) -> Transaction:
        transactions = self.list_transactions()
        for index, item in enumerate(transactions):
            if item.id == transaction_id:
                updated = item.model_copy(update={"taxed": status})
                transactions[index] = updated
                self._write_transactions(transactions)
                return updated
        raise ValueError(f"Transaction {transaction_id} not found")

    def mark_transaction_taxed(self, transaction_id: str) -> Transaction:
        return self.set_transaction_tax_status(transaction_id, TaxStatus.YES)

    def mark_transaction_untaxed(self, transaction_id: str) -> Transaction:
        return self.set_transaction_tax_status(transaction_id, TaxStatus.NO)

    # Tax settlements ---------------------------------------------------------------
    def list_tax_settlements(self) -> list[TaxSettlementRecord]:
        payload = json.loads(self._tax_settlements_path.read_text(encoding="utf-8") or "[]")
        records: list[TaxSettlementRecord] = []
        changed = False
        for item in payload:
            data = dict(item)
            if not data.get("id"):
                data["id"] = str(uuid4())
                changed = True
            if not data.get("recorded_at"):
                data["recorded_at"] = date.today().isoformat()
                changed = True

            currency_value = data.get("currency")
            if isinstance(currency_value, str):
                try:
                    data["currency"] = Currency(currency_value)
                except ValueError:
                    data["currency"] = Currency.JPY
                    changed = True

            amount_value = data.get("amount")
            if isinstance(amount_value, str):
                try:
                    data["amount"] = float(amount_value)
                except ValueError:
                    data["amount"] = 0.0
                    changed = True

            exchange_rate = data.get("exchange_rate")
            if exchange_rate in ("", None):
                data["exchange_rate"] = None
            elif isinstance(exchange_rate, str):
                try:
                    data["exchange_rate"] = float(exchange_rate)
                except ValueError:
                    data["exchange_rate"] = None
                    changed = True

            jpy_equivalent = data.get("jpy_equivalent")
            if isinstance(jpy_equivalent, str):
                try:
                    data["jpy_equivalent"] = float(jpy_equivalent)
                except ValueError:
                    data["jpy_equivalent"] = None
                    changed = True

            record = TaxSettlementRecord(**data)
            normalized = record.model_dump(mode="json")
            if normalized != data:
                changed = True
            records.append(record)
        if changed:
            self._write_tax_settlements(records)
        return records

    def get_tax_settlement(self, settlement_id: str) -> TaxSettlementRecord:
        for record in self.list_tax_settlements():
            if record.id == settlement_id:
                return record
        raise ValueError(f"Tax settlement {settlement_id} not found")

    def add_tax_settlement(self, settlement: TaxSettlementRecord) -> TaxSettlementRecord:
        settlements = self.list_tax_settlements()
        settlements.append(settlement)
        self._write_tax_settlements(settlements)
        return settlement

    def update_tax_settlement(
        self, settlement_id: str, updated: TaxSettlementRecord
    ) -> TaxSettlementRecord:
        settlements = self.list_tax_settlements()
        for index, record in enumerate(settlements):
            if record.id == settlement_id:
                settlements[index] = updated
                self._write_tax_settlements(settlements)
                return updated
        raise ValueError(f"Tax settlement {settlement_id} not found")

    def delete_tax_settlement(self, settlement_id: str) -> None:
        settlements = self.list_tax_settlements()
        updated = [item for item in settlements if item.id != settlement_id]
        if len(updated) == len(settlements):
            raise ValueError(f"Tax settlement {settlement_id} not found")
        self._write_tax_settlements(updated)

    def _write_tax_settlements(self, settlements: Iterable[TaxSettlementRecord]) -> None:
        serialized = [record.model_dump(mode="json") for record in settlements]
        self._tax_settlements_path.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
        )
