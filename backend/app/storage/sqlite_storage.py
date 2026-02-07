from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from ..models.schemas import (
    FxExchangeRecord,
    FundingCapitalAdjustment,
    FundingGroup,
    QuoteRecord,
    TaxSettlementRecord,
    Transaction,
)


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
            cross_currency INTEGER NOT NULL DEFAULT 0,
            buy_currency TEXT,
            sell_currency TEXT,
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

        CREATE TABLE IF NOT EXISTS capital_adjustments (
            id TEXT PRIMARY KEY,
            funding_group TEXT NOT NULL,
            amount REAL NOT NULL,
            effective_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (funding_group) REFERENCES funding_groups(name)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_capital_adjustments_group
            ON capital_adjustments (funding_group, effective_date);

        CREATE TABLE IF NOT EXISTS fx_exchanges (
            id TEXT PRIMARY KEY,
            transaction_id TEXT,
            exchange_date TEXT NOT NULL,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            from_amount REAL NOT NULL,
            to_amount REAL NOT NULL,
            rate REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id)
                ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fx_exchanges_date
            ON fx_exchanges (exchange_date, id);
        CREATE INDEX IF NOT EXISTS idx_fx_exchanges_transaction
            ON fx_exchanges (transaction_id);

        CREATE TABLE IF NOT EXISTS quotes (
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL,
            as_of TEXT NOT NULL,
            PRIMARY KEY (symbol, market)
        );
        CREATE INDEX IF NOT EXISTS idx_quotes_as_of
            ON quotes (as_of);
        """
        with self._connect() as connection:
            connection.executescript(schema)
            self._migrate_transactions_schema(connection)

    def _migrate_transactions_schema(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(transactions);").fetchall()
        }
        if "cross_currency" not in columns:
            connection.execute(
                "ALTER TABLE transactions ADD COLUMN cross_currency INTEGER NOT NULL DEFAULT 0;"
            )
        if "buy_currency" not in columns:
            connection.execute("ALTER TABLE transactions ADD COLUMN buy_currency TEXT;")
        if "sell_currency" not in columns:
            connection.execute("ALTER TABLE transactions ADD COLUMN sell_currency TEXT;")

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
                1 if tx.cross_currency else 0,
                getattr(tx.buy_currency, "value", tx.buy_currency),
                getattr(tx.sell_currency, "value", tx.sell_currency),
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
                        funding_group, cash_currency, cross_currency, buy_currency,
                        sell_currency, market, taxed, memo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def replace_capital_adjustments(
        self, adjustments: Iterable[FundingCapitalAdjustment]
    ) -> None:
        rows: Sequence[tuple] = [
            (
                adjustment.id,
                adjustment.funding_group,
                float(adjustment.amount),
                adjustment.effective_date.isoformat(),
                adjustment.notes,
            )
            for adjustment in adjustments
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM capital_adjustments;")
            if rows:
                connection.executemany(
                    """
                    INSERT INTO capital_adjustments (
                        id, funding_group, amount, effective_date, notes
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def replace_fx_exchanges(self, exchanges: Iterable[FxExchangeRecord]) -> None:
        rows: Sequence[tuple] = [
            (
                exchange.id,
                exchange.transaction_id,
                exchange.exchange_date.isoformat(),
                getattr(exchange.from_currency, "value", exchange.from_currency),
                getattr(exchange.to_currency, "value", exchange.to_currency),
                float(exchange.from_amount),
                float(exchange.to_amount),
                float(exchange.rate),
                exchange.notes,
            )
            for exchange in exchanges
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM fx_exchanges;")
            if rows:
                connection.executemany(
                    """
                    INSERT INTO fx_exchanges (
                        id, transaction_id, exchange_date, from_currency, to_currency,
                        from_amount, to_amount, rate, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def replace_quotes(self, quotes: Iterable[QuoteRecord]) -> None:
        rows: Sequence[tuple] = [
            (
                quote.symbol,
                getattr(quote.market, "value", quote.market),
                float(quote.price),
                getattr(quote.currency, "value", quote.currency),
                quote.as_of.isoformat(),
            )
            for quote in quotes
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM quotes;")
            if rows:
                connection.executemany(
                    """
                    INSERT INTO quotes (symbol, market, price, currency, as_of)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    rows,
                )
    # Read helpers
    def load_transactions(self) -> list[Transaction]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, trade_date, symbol, quantity, gross_amount, funding_group,"
                " cash_currency, cross_currency, buy_currency, sell_currency, market,"
                " taxed, memo FROM transactions"
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

    def load_capital_adjustments(self) -> list[FundingCapitalAdjustment]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, funding_group, amount, effective_date, notes"
                " FROM capital_adjustments ORDER BY effective_date, id;"
            ).fetchall()
        return [FundingCapitalAdjustment(**dict(row)) for row in rows]

    def load_fx_exchanges(self) -> list[FxExchangeRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, transaction_id, exchange_date, from_currency, to_currency,"
                " from_amount, to_amount, rate, notes"
                " FROM fx_exchanges ORDER BY exchange_date, id;"
            ).fetchall()
        return [FxExchangeRecord(**dict(row)) for row in rows]

    def load_quotes(self) -> list[QuoteRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT symbol, market, price, currency, as_of FROM quotes"
            ).fetchall()
        return [QuoteRecord(**dict(row)) for row in rows]

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
            if cursor.fetchone():
                return True
            cursor = connection.execute("SELECT 1 FROM capital_adjustments LIMIT 1;")
            if cursor.fetchone():
                return True
            cursor = connection.execute("SELECT 1 FROM fx_exchanges LIMIT 1;")
            if cursor.fetchone():
                return True
            cursor = connection.execute("SELECT 1 FROM quotes LIMIT 1;")
            return cursor.fetchone() is not None
