from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, TypeVar
from uuid import uuid4

from ..models.schemas import (
    AnnualTaxSettlement,
    AnnualTaxSettlementCreate,
    AnnualTaxSettlementUpdate,
    BrokerAccountType,
    Currency,
    FxExchangeCreate,
    FxExchangeRecord,
    FundingCapitalAdjustment,
    FundingCapitalAdjustmentCreate,
    FundingGroup,
    FundingGroupUpdate,
    QuoteRecord,
    RealizedPnLRecord,
    StockSplitCreate,
    StockSplitRecord,
    SuspiciousDuplicateGroup,
    SuspiciousDuplicateResponse,
    TaxSettlementRecord,
    TaxStatus,
    Transaction,
    TransactionCreate,
)
from .sqlite_storage import SQLiteStorage


T = TypeVar("T")


def _normalize_memo(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def transaction_business_fingerprint(transaction: Transaction) -> str:
    trade_currency = transaction.trade_currency or transaction.cash_currency
    trade_amount = transaction.trade_amount or transaction.gross_amount
    settlement_currency = transaction.settlement_currency or transaction.cash_currency
    settlement_amount = transaction.settlement_amount or transaction.gross_amount
    return "|".join(
        [
            transaction.trade_date.isoformat(),
            transaction.symbol.strip().upper(),
            transaction.market.value,
            f"{transaction.quantity:.8f}",
            f"{transaction.gross_amount:.8f}",
            transaction.funding_group.strip(),
            transaction.cash_currency.value,
            (transaction.position_group or "").strip(),
            (transaction.settlement_group or "").strip(),
            trade_currency.value,
            f"{trade_amount:.8f}",
            settlement_currency.value,
            f"{settlement_amount:.8f}",
            transaction.broker_account_type.value,
            "1" if transaction.cross_currency else "0",
            transaction.buy_currency.value if transaction.buy_currency else "",
            transaction.sell_currency.value if transaction.sell_currency else "",
            transaction.taxed.value,
            _normalize_memo(transaction.memo),
        ]
    )


class LocalDataRepository:
    """Simple JSON-backed repository for local single-user use."""

    def __init__(self, base_path: Path | None = None) -> None:
        # 支持分别为 JSON 与 SQLite 配置独立路径：
        # - KABUCOUNT_JSON_DIR：JSON 文件目录
        # - KABUCOUNT_SQLITE_DIR：SQLite 数据库存放目录
        # 回退逻辑：
        # 1. 如果 base_path 显式传入，则 JSON 使用 base_path；
        # 2. 否则如果定义了 KABUCOUNT_JSON_DIR，则 JSON 使用该目录；
        # 3. 否则回退到：KABUCOUNT_DATA_DIR 或 项目根下的 data 目录。
        # SQLite 默认：
        # - 如果定义了 KABUCOUNT_SQLITE_DIR，则使用该目录；
        # - 否则与 JSON 使用同一目录，保持向后兼容。
        env_data_dir = os.environ.get("KABUCOUNT_DATA_DIR")
        env_json_dir = os.environ.get("KABUCOUNT_JSON_DIR")
        env_sqlite_dir = os.environ.get("KABUCOUNT_SQLITE_DIR")

        default_base = (
            Path(env_data_dir)
            if env_data_dir
            else Path(__file__).resolve().parents[3] / "data"
        )

        if base_path is not None:
            json_base = base_path
        elif env_json_dir:
            json_base = Path(env_json_dir)
        else:
            json_base = default_base

        if env_sqlite_dir:
            sqlite_base = Path(env_sqlite_dir)
        else:
            sqlite_base = json_base

        self.base_path = json_base
        self.base_path.mkdir(parents=True, exist_ok=True)
        sqlite_base.mkdir(parents=True, exist_ok=True)

        self._transactions_path = self.base_path / "transactions.json"
        self._funding_groups_path = self.base_path / "funding_groups.json"
        self._tax_settlements_path = self.base_path / "tax_settlements.json"
        self._annual_tax_settlements_path = self.base_path / "annual_tax_settlements.json"
        self._realized_pnl_path = self.base_path / "realized_pnl.json"
        self._capital_adjustments_path = self.base_path / "capital_adjustments.json"
        self._stock_splits_path = self.base_path / "stock_splits.json"
        self._fx_exchanges_path = self.base_path / "fx_exchanges.json"
        self._quotes_path = self.base_path / "quotes.json"
        for path in (
            self._transactions_path,
            self._funding_groups_path,
            self._tax_settlements_path,
            self._annual_tax_settlements_path,
            self._realized_pnl_path,
            self._capital_adjustments_path,
            self._stock_splits_path,
            self._fx_exchanges_path,
            self._quotes_path,
        ):
            if not path.exists():
                path.write_text("[]", encoding="utf-8")

        self.sqlite = SQLiteStorage(sqlite_base / "kabumemo.db")
        if not self.sqlite.has_data():
            self._sync_sqlite_from_files()

    def _sync_sqlite_from_files(self) -> None:
        """Mirror current JSON files into SQLite storage."""
        transactions = self.list_transactions()
        groups = self.list_funding_groups()
        settlements = self.list_tax_settlements()
        capital_adjustments = self.list_capital_adjustments()
        stock_splits = self.list_stock_splits()
        annual_tax_settlements = self.list_annual_tax_settlements()
        realized_pnl_records = self.list_realized_pnl_records()
        fx_exchanges = self.list_fx_exchanges()
        quotes = self.list_quotes()
        self.sqlite.replace_transactions(transactions)
        self.sqlite.replace_funding_groups(groups)
        self.sqlite.replace_tax_settlements(settlements)
        self.sqlite.replace_annual_tax_settlements(annual_tax_settlements)
        self.sqlite.replace_realized_pnl_records(realized_pnl_records)
        self.sqlite.replace_capital_adjustments(capital_adjustments)
        self.sqlite.replace_stock_splits(stock_splits)
        self.sqlite.replace_fx_exchanges(fx_exchanges)
        self.sqlite.replace_quotes(quotes)

    def sync_sqlite_from_json(self) -> None:
        """Public helper to mirror JSON source data into SQLite."""
        self._sync_sqlite_from_files()

    def sqlite_has_data(self) -> bool:
        return self.sqlite.has_data()

    def _write_with_mirror(
        self,
        path: Path,
        records: Iterable[T],
        serializer: Callable[[T], dict],
        mirror: Callable[[Sequence[T]], None],
        restore_factory: Callable[[dict], T],
    ) -> None:
        items = list(records)
        serialized = [serializer(item) for item in items]
        previous_content = path.read_text(encoding="utf-8") if path.exists() else "[]"
        try:
            mirror(items)
            path.write_text(
                json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            try:
                payload = json.loads(previous_content or "[]")
                restore_items = [restore_factory(entry) for entry in payload]
                mirror(restore_items)
            except Exception:
                pass
            raise

    # Transactions -----------------------------------------------------------------
    def list_transactions(self) -> List[Transaction]:
        payload = json.loads(self._transactions_path.read_text(encoding="utf-8") or "[]")
        records: list[Transaction] = []
        for item in payload:
            data = dict(item)
            if "cross_currency" not in data:
                data["cross_currency"] = False
            if "buy_currency" not in data:
                data["buy_currency"] = None
            if "sell_currency" not in data:
                data["sell_currency"] = None
            if "position_group" not in data:
                data["position_group"] = data.get("funding_group")
            if "settlement_group" not in data:
                data["settlement_group"] = data.get("funding_group")
            if "trade_currency" not in data:
                data["trade_currency"] = Currency.USD if data.get("market") == "US" else data.get("cash_currency")
            if "trade_amount" not in data:
                data["trade_amount"] = data.get("gross_amount")
            if "settlement_currency" not in data:
                data["settlement_currency"] = data.get("cash_currency")
            if "settlement_amount" not in data:
                data["settlement_amount"] = data.get("gross_amount")
            if "broker_account_type" not in data:
                data["broker_account_type"] = BrokerAccountType.UNKNOWN
            records.append(Transaction(**data))
        return records

    def list_transactions_from_sqlite(self) -> List[Transaction]:
        return self.sqlite.load_transactions()

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
        self._write_with_mirror(
            self._transactions_path,
            transactions,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_transactions,
            lambda payload: Transaction(**payload),
        )

    # Funding groups ----------------------------------------------------------------
    def list_funding_groups(self) -> List[FundingGroup]:
        payload = json.loads(self._funding_groups_path.read_text(encoding="utf-8") or "[]")
        return [FundingGroup(**item) for item in payload]

    def list_funding_groups_from_sqlite(self) -> List[FundingGroup]:
        return self.sqlite.load_funding_groups()

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
        self._write_with_mirror(
            self._funding_groups_path,
            groups,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_funding_groups,
            lambda payload: FundingGroup(**payload),
        )

    # Utility -----------------------------------------------------------------------
    def ensure_default_groups(self) -> None:
        if self.list_funding_groups():
            return
        defaults = [
            FundingGroup(name="JPY", currency=Currency.JPY, initial_amount=0.0),
            FundingGroup(name="USD", currency=Currency.USD, initial_amount=0.0),
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

            balance_exchange_rate = data.get("balance_exchange_rate")
            if balance_exchange_rate in ("", None):
                data["balance_exchange_rate"] = None
            elif isinstance(balance_exchange_rate, str):
                try:
                    data["balance_exchange_rate"] = float(balance_exchange_rate)
                except ValueError:
                    data["balance_exchange_rate"] = None
                    changed = True

            jpy_equivalent = data.get("jpy_equivalent")
            if isinstance(jpy_equivalent, str):
                try:
                    data["jpy_equivalent"] = float(jpy_equivalent)
                except ValueError:
                    data["jpy_equivalent"] = None
                    changed = True

            if data.get("currency") == Currency.USD and data.get("exchange_rate") is None:
                if data.get("jpy_equivalent") is not None:
                    data["amount"] = data["jpy_equivalent"]
                data["currency"] = Currency.JPY
                changed = True

            balance_usd_required = data.get("balance_usd_required")
            if isinstance(balance_usd_required, str):
                try:
                    data["balance_usd_required"] = float(balance_usd_required)
                except ValueError:
                    data["balance_usd_required"] = None
                    changed = True

            record = TaxSettlementRecord(**data)
            normalized = record.model_dump(mode="json")
            if normalized != data:
                changed = True
            records.append(record)
        if changed:
            self._write_tax_settlements(records)
        return records

    def list_tax_settlements_from_sqlite(self) -> list[TaxSettlementRecord]:
        return self.sqlite.load_tax_settlements()

    def list_annual_tax_settlements(self) -> list[AnnualTaxSettlement]:
        payload = json.loads(self._annual_tax_settlements_path.read_text(encoding="utf-8") or "[]")
        return [AnnualTaxSettlement(**item) for item in payload]

    def list_annual_tax_settlements_from_sqlite(self) -> list[AnnualTaxSettlement]:
        return self.sqlite.load_annual_tax_settlements()

    def list_realized_pnl_records(self) -> list[RealizedPnLRecord]:
        payload = json.loads(self._realized_pnl_path.read_text(encoding="utf-8") or "[]")
        return [RealizedPnLRecord(**item) for item in payload]

    def list_realized_pnl_records_from_sqlite(self) -> list[RealizedPnLRecord]:
        return self.sqlite.load_realized_pnl_records()

    def replace_realized_pnl_records(self, records: Iterable[RealizedPnLRecord]) -> None:
        self._write_with_mirror(
            self._realized_pnl_path,
            records,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_realized_pnl_records,
            lambda payload: RealizedPnLRecord(**payload),
        )

    def add_annual_tax_settlement(
        self, payload: AnnualTaxSettlementCreate
    ) -> AnnualTaxSettlement:
        record = AnnualTaxSettlement(id=str(uuid4()), **payload.model_dump())
        records = self.list_annual_tax_settlements()
        records.append(record)
        self._write_annual_tax_settlements(records)
        return record

    def update_annual_tax_settlement(
        self, settlement_id: str, payload: AnnualTaxSettlementUpdate
    ) -> AnnualTaxSettlement:
        records = self.list_annual_tax_settlements()
        for index, record in enumerate(records):
            if record.id == settlement_id:
                updated = record.model_copy(update=payload.model_dump(exclude_unset=True))
                records[index] = updated
                self._write_annual_tax_settlements(records)
                return updated
        raise ValueError(f"Annual tax settlement {settlement_id} not found")

    def delete_annual_tax_settlement(self, settlement_id: str) -> None:
        records = self.list_annual_tax_settlements()
        updated = [item for item in records if item.id != settlement_id]
        if len(updated) == len(records):
            raise ValueError(f"Annual tax settlement {settlement_id} not found")
        self._write_annual_tax_settlements(updated)

    def replace_transactions(self, transactions: Iterable[Transaction]) -> None:
        self._write_transactions(transactions)

    def _resolve_transaction_merge(
        self, transactions: Iterable[Transaction]
    ) -> tuple[list[Transaction], list[Transaction], int]:
        existing_transactions = self.list_transactions()
        seen_ids = {item.id for item in existing_transactions}
        seen_fingerprints = {
            transaction_business_fingerprint(item) for item in existing_transactions
        }
        merged_transactions = list(existing_transactions)
        applied_transactions: list[Transaction] = []
        skipped_count = 0

        for transaction in transactions:
            fingerprint = transaction_business_fingerprint(transaction)
            if transaction.id in seen_ids or fingerprint in seen_fingerprints:
                skipped_count += 1
                continue
            merged_transactions.append(transaction)
            seen_ids.add(transaction.id)
            seen_fingerprints.add(fingerprint)
            applied_transactions.append(transaction)

        return merged_transactions, applied_transactions, skipped_count

    def preview_transactions_skip_duplicates(
        self, transactions: Iterable[Transaction]
    ) -> tuple[list[Transaction], int]:
        _, applied_transactions, skipped_count = self._resolve_transaction_merge(transactions)
        return applied_transactions, skipped_count

    def merge_transactions_skip_duplicates(
        self, transactions: Iterable[Transaction]
    ) -> tuple[list[Transaction], list[Transaction], int]:
        merged_transactions, applied_transactions, skipped_count = self._resolve_transaction_merge(
            transactions
        )

        if applied_transactions:
            self._write_transactions(merged_transactions)

        return merged_transactions, applied_transactions, skipped_count

    def find_suspicious_duplicate_transactions(self) -> SuspiciousDuplicateResponse:
        groups_by_fingerprint: dict[str, list[Transaction]] = defaultdict(list)
        for transaction in self.list_transactions():
            groups_by_fingerprint[transaction_business_fingerprint(transaction)].append(transaction)

        groups: list[SuspiciousDuplicateGroup] = []
        duplicate_transaction_count = 0
        suggested_delete_count = 0
        for fingerprint, transactions in groups_by_fingerprint.items():
            if len(transactions) < 2:
                continue
            sorted_transactions = sorted(
                transactions,
                key=lambda item: (item.trade_date, item.symbol, item.quantity, item.id),
            )
            suggested_delete_ids = [item.id for item in sorted_transactions[1:]]
            groups.append(
                SuspiciousDuplicateGroup(
                    group_id=hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16],
                    reason=(
                        "Transactions match on date, symbol, quantities, amounts, groups, "
                        "currencies, account type, tax status, and memo."
                    ),
                    transactions=sorted_transactions,
                    suggested_delete_ids=suggested_delete_ids,
                )
            )
            duplicate_transaction_count += len(sorted_transactions)
            suggested_delete_count += len(suggested_delete_ids)

        groups.sort(
            key=lambda group: (
                -len(group.transactions),
                group.transactions[0].trade_date,
                group.transactions[0].symbol,
            )
        )
        return SuspiciousDuplicateResponse(
            groups=groups,
            duplicate_transaction_count=duplicate_transaction_count,
            suggested_delete_count=suggested_delete_count,
        )

    def delete_transactions(self, transaction_ids: Iterable[str]) -> list[str]:
        deduped_ids = list(dict.fromkeys(transaction_ids))
        transactions = self.list_transactions()
        existing_ids = {transaction.id for transaction in transactions}
        missing_ids = [transaction_id for transaction_id in deduped_ids if transaction_id not in existing_ids]
        if missing_ids:
            raise ValueError(f"Transaction {missing_ids[0]} not found")

        delete_id_set = set(deduped_ids)
        remaining_transactions = [
            transaction for transaction in transactions if transaction.id not in delete_id_set
        ]
        self._write_transactions(remaining_transactions)

        settlements = self.list_tax_settlements()
        filtered_settlements = [
            item for item in settlements if item.transaction_id not in delete_id_set
        ]
        if len(filtered_settlements) != len(settlements):
            self._write_tax_settlements(filtered_settlements)

        return deduped_ids

    def _write_annual_tax_settlements(
        self, settlements: Iterable[AnnualTaxSettlement]
    ) -> None:
        self._write_with_mirror(
            self._annual_tax_settlements_path,
            settlements,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_annual_tax_settlements,
            lambda payload: AnnualTaxSettlement(**payload),
        )

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
        self._write_with_mirror(
            self._tax_settlements_path,
            settlements,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_tax_settlements,
            lambda payload: TaxSettlementRecord(**payload),
        )

    def clear_tax_settlements(self) -> None:
        self._write_tax_settlements([])

    # Capital adjustments ---------------------------------------------------------
    def list_capital_adjustments(self) -> list[FundingCapitalAdjustment]:
        payload = json.loads(self._capital_adjustments_path.read_text(encoding="utf-8") or "[]")
        records = [FundingCapitalAdjustment(**item) for item in payload]
        return sorted(records, key=lambda item: (item.effective_date, item.id))

    def list_capital_adjustments_from_sqlite(self) -> list[FundingCapitalAdjustment]:
        return self.sqlite.load_capital_adjustments()

    def list_capital_adjustments_for_group(self, name: str) -> list[FundingCapitalAdjustment]:
        return [item for item in self.list_capital_adjustments() if item.funding_group == name]

    def add_capital_adjustment(
        self, payload: FundingCapitalAdjustmentCreate
    ) -> FundingCapitalAdjustment:
        record = FundingCapitalAdjustment(id=str(uuid4()), **payload.model_dump())
        records = self.list_capital_adjustments()
        records.append(record)
        self._write_capital_adjustments(records)
        return record

    def _write_capital_adjustments(
        self, adjustments: Iterable[FundingCapitalAdjustment]
    ) -> None:
        self._write_with_mirror(
            self._capital_adjustments_path,
            adjustments,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_capital_adjustments,
            lambda payload: FundingCapitalAdjustment(**payload),
        )

    def list_stock_splits(self) -> list[StockSplitRecord]:
        payload = json.loads(self._stock_splits_path.read_text(encoding="utf-8") or "[]")
        records = [StockSplitRecord(**item) for item in payload]
        return sorted(records, key=lambda item: (item.effective_date, item.symbol, item.id))

    def list_stock_splits_from_sqlite(self) -> list[StockSplitRecord]:
        return self.sqlite.load_stock_splits()

    def add_stock_split(self, payload: StockSplitCreate) -> StockSplitRecord:
        record = StockSplitRecord(id=str(uuid4()), **payload.model_dump())
        records = self.list_stock_splits()
        records.append(record)
        self._write_stock_splits(records)
        return record

    def delete_stock_split(self, split_id: str) -> None:
        records = self.list_stock_splits()
        updated = [item for item in records if item.id != split_id]
        if len(updated) == len(records):
            raise ValueError(f"Stock split {split_id} not found")
        self._write_stock_splits(updated)

    def _write_stock_splits(self, records: Iterable[StockSplitRecord]) -> None:
        self._write_with_mirror(
            self._stock_splits_path,
            records,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_stock_splits,
            lambda payload: StockSplitRecord(**payload),
        )

    # FX exchanges ----------------------------------------------------------------
    def list_fx_exchanges(self) -> list[FxExchangeRecord]:
        payload = json.loads(self._fx_exchanges_path.read_text(encoding="utf-8") or "[]")
        records: list[FxExchangeRecord] = []
        for item in payload:
            data = dict(item)
            if "to_amount" not in data or data["to_amount"] in (None, ""):
                rate = data.get("rate") or 0.0
                from_amount = float(data.get("from_amount") or 0.0)
                if data.get("from_currency") == Currency.JPY and data.get("to_currency") == Currency.USD:
                    data["to_amount"] = from_amount / rate if rate else 0.0
                elif data.get("from_currency") == Currency.USD and data.get("to_currency") == Currency.JPY:
                    data["to_amount"] = from_amount * rate if rate else 0.0
                else:
                    data["to_amount"] = from_amount
            records.append(FxExchangeRecord(**data))
        return sorted(records, key=lambda item: (item.exchange_date, item.id))

    def list_fx_exchanges_from_sqlite(self) -> list[FxExchangeRecord]:
        return self.sqlite.load_fx_exchanges()

    def add_fx_exchange(self, payload: FxExchangeCreate) -> FxExchangeRecord:
        record = FxExchangeRecord(id=str(uuid4()), **payload.model_dump())
        records = self.list_fx_exchanges()
        records.append(record)
        self._write_fx_exchanges(records)
        return record

    def delete_fx_exchange(self, exchange_id: str) -> None:
        records = self.list_fx_exchanges()
        updated = [item for item in records if item.id != exchange_id]
        if len(updated) == len(records):
            raise ValueError(f"FX exchange {exchange_id} not found")
        self._write_fx_exchanges(updated)

    def _write_fx_exchanges(self, exchanges: Iterable[FxExchangeRecord]) -> None:
        self._write_with_mirror(
            self._fx_exchanges_path,
            exchanges,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_fx_exchanges,
            lambda payload: FxExchangeRecord(**payload),
        )

    # Quotes ----------------------------------------------------------------
    def list_quotes(self) -> list[QuoteRecord]:
        payload = json.loads(self._quotes_path.read_text(encoding="utf-8") or "[]")
        records = [QuoteRecord(**item) for item in payload]
        return records

    def list_quotes_from_sqlite(self) -> list[QuoteRecord]:
        return self.sqlite.load_quotes()

    def replace_quotes(self, quotes: Iterable[QuoteRecord]) -> None:
        self._write_with_mirror(
            self._quotes_path,
            quotes,
            lambda item: item.model_dump(mode="json"),
            self.sqlite.replace_quotes,
            lambda payload: QuoteRecord(**payload),
        )
