from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from ..models.schemas import FundingGroup, TaxSettlementRecord, Transaction


class SQLiteStorage:
    """Lightweight SQLite persistence for Kabumemo data."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        try:
            yield connection
            connection.commit()
        except Exception:  # pragma: no cover - defensive rollback
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        schema = """
        PRAGMA journal_mode = WAL;

        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL,
            gross_amount REAL NOT NULL,
            funding_group TEXT NOT NULL,
            cash_currency TEXT NOT NULL,
            market TEXT NOT NULL,
            taxed TEXT NOT NULL,
            memo TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_transactions_trade_date
            ON transactions (trade_date, symbol);

        CREATE TABLE IF NOT EXISTS funding_groups (
            name TEXT PRIMARY KEY,
            currency TEXT NOT NULL,
            initial_amount REAL NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS tax_settlements (
            id TEXT PRIMARY KEY,
            transaction_id TEXT NOT NULL,
            funding_group TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            exchange_rate REAL,
            jpy_equivalent REAL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_tax_settlements_transaction
            ON tax_settlements (transaction_id);
        """
        with self._connect() as connection:
            connection.executescript(schema)

    # ------------------------------------------------------------------
    # Bulk mirror helpers
    def replace_transactions(self, transactions: Iterable[Transaction]) -> None:
        rows: Sequence[tuple] = [
            (
                tx.id,
                tx.trade_date.isoformat(),
                tx.symbol,
                float(tx.quantity),
                float(tx.gross_amount),
                tx.funding_group,
                getattr(tx.cash_currency, "value", tx.cash_currency),
                getattr(tx.market, "value", tx.market),
                getattr(tx.taxed, "value", tx.taxed),
                tx.memo,
            )
            for tx in transactions
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM transactions;")
            if rows:
                connection.executemany(
                    """
                    INSERT INTO transactions (
                        id, trade_date, symbol, quantity, gross_amount,
                        funding_group, cash_currency, market, taxed, memo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def replace_funding_groups(self, groups: Iterable[FundingGroup]) -> None:
        rows: Sequence[tuple] = [
            (
                group.name,
                getattr(group.currency, "value", group.currency),
                float(group.initial_amount),
                group.notes,
            )
            for group in groups
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM funding_groups;")
            if rows:
                connection.executemany(
                    """
                    INSERT INTO funding_groups (
                        name, currency, initial_amount, notes
                    ) VALUES (?, ?, ?, ?)
                    """,
                    rows,
                )

    def replace_tax_settlements(self, settlements: Iterable[TaxSettlementRecord]) -> None:
        rows: Sequence[tuple] = [
            (
                settlement.id,
                settlement.transaction_id,
                settlement.funding_group,
                float(settlement.amount),
                getattr(settlement.currency, "value", settlement.currency),
                settlement.exchange_rate,
                settlement.jpy_equivalent,
                settlement.recorded_at.isoformat(),
            )
            for settlement in settlements
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM tax_settlements;")
            if rows:
                connection.executemany(
                    """
                    INSERT INTO tax_settlements (
                        id, transaction_id, funding_group, amount,
                        currency, exchange_rate, jpy_equivalent, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    # ------------------------------------------------------------------
    # Read helpers
    def load_transactions(self) -> list[Transaction]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, trade_date, symbol, quantity, gross_amount, funding_group,"
                " cash_currency, market, taxed, memo FROM transactions"
                " ORDER BY trade_date, id;"
            ).fetchall()
        return [Transaction(**dict(row)) for row in rows]

    def load_funding_groups(self) -> list[FundingGroup]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name, currency, initial_amount, notes FROM funding_groups"
                " ORDER BY name;"
            ).fetchall()
        return [FundingGroup(**dict(row)) for row in rows]

    def load_tax_settlements(self) -> list[TaxSettlementRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, transaction_id, funding_group, amount, currency,"
                " exchange_rate, jpy_equivalent, recorded_at"
                " FROM tax_settlements ORDER BY recorded_at, id;"
            ).fetchall()
        return [TaxSettlementRecord(**dict(row)) for row in rows]

    def has_data(self) -> bool:
        query = "SELECT 1 FROM transactions LIMIT 1;"
        with self._connect() as connection:
            cursor = connection.execute(query)
            if cursor.fetchone():
                return True
            cursor = connection.execute("SELECT 1 FROM funding_groups LIMIT 1;")
            if cursor.fetchone():
                return True
            cursor = connection.execute("SELECT 1 FROM tax_settlements LIMIT 1;")
            return cursor.fetchone() is not None
