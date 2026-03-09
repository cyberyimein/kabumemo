from __future__ import annotations

import base64
import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from ..models.schemas import (
    BrokerAccountType,
    BrokerImportApplyRequest,
    BrokerImportFile,
    BrokerImportPreviewItem,
    BrokerImportPreviewRequest,
    BrokerImportPreviewResponse,
    Currency,
    Market,
    TaxStatus,
    Transaction,
)


def _decode_file(file: BrokerImportFile) -> str:
    raw = base64.b64decode(file.content_base64)
    candidates = [file.encoding_hint, "utf-8-sig", "utf-8", "cp932"]
    for encoding in candidates:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace")


def _reader_from_text(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def _find_header_index(rows: list[list[str]], header_name: str) -> int:
    for index, row in enumerate(rows):
        if row and row[0].strip() == header_name:
            return index
    raise ValueError(f"Header row not found: {header_name}")


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y/%m/%d").date()


def _parse_money(value: str) -> tuple[float, Currency]:
    cleaned = value.replace(",", "").strip()
    if cleaned.endswith("円"):
        return float(cleaned[:-1]), Currency.JPY
    if cleaned.endswith("USD"):
        return float(cleaned[:-3]), Currency.USD
    return float(cleaned), Currency.JPY


def _parse_unit_price(value: str) -> tuple[float, Currency]:
    cleaned = value.replace(",", "").strip()
    if cleaned.endswith("USD"):
        return float(cleaned[:-3]), Currency.USD
    return float(cleaned), Currency.JPY


def _normalize_account_type(value: str) -> BrokerAccountType:
    normalized = value.strip().upper()
    if "NISA" in normalized:
        return BrokerAccountType.NISA
    if "特定" in value:
        return BrokerAccountType.SPECIFIC
    if value.strip():
        return BrokerAccountType.GENERAL
    return BrokerAccountType.UNKNOWN


def _stable_transaction_id(parts: Iterable[str]) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


def _default_tax_status(account_type: BrokerAccountType, quantity: float) -> TaxStatus:
    if quantity > 0:
        return TaxStatus.YES
    return TaxStatus.YES if account_type == BrokerAccountType.NISA else TaxStatus.NO


def _build_item(
    *,
    trade_date: date,
    symbol: str,
    market: Market,
    quantity: float,
    trade_currency: Currency,
    trade_amount: float,
    settlement_currency: Currency,
    settlement_amount: float,
    account_type: BrokerAccountType,
    position_group: str,
    settlement_group: str,
    source_file: str,
    source_line: int,
    memo: str | None = None,
) -> BrokerImportPreviewItem:
    transaction_id = _stable_transaction_id(
        [
            source_file,
            str(source_line),
            trade_date.isoformat(),
            symbol,
            market.value,
            f"{quantity:.8f}",
            trade_currency.value,
            f"{trade_amount:.8f}",
            settlement_currency.value,
            f"{settlement_amount:.8f}",
        ]
    )
    return BrokerImportPreviewItem(
        trade_date=trade_date,
        symbol=symbol,
        market=market,
        quantity=quantity,
        trade_currency=trade_currency,
        trade_amount=round(abs(trade_amount), 4),
        settlement_currency=settlement_currency,
        settlement_amount=round(abs(settlement_amount), 4),
        broker_account_type=account_type,
        position_group=position_group,
        settlement_group=settlement_group,
        source_file=source_file,
        source_line=source_line,
        transaction_id=transaction_id,
        taxed=_default_tax_status(account_type, quantity),
        memo=memo,
    )


def _parse_domestic_rows(
    rows: list[list[str]],
    request: BrokerImportPreviewRequest,
    file_name: str,
) -> list[BrokerImportPreviewItem]:
    start = _find_header_index(rows, "約定日") + 1
    items: list[BrokerImportPreviewItem] = []
    for line_number, row in enumerate(rows[start:], start=start + 1):
        if len(row) < 14 or not row[0].strip():
            continue
        trade_kind = row[4].strip()
        if "買" in trade_kind:
            quantity = float(row[8])
        elif "売" in trade_kind:
            quantity = -float(row[8])
        else:
            continue

        settlement_amount = float(str(row[13]).replace(",", "").strip())
        unit_price = float(str(row[9]).replace(",", "").strip())
        items.append(
            _build_item(
                trade_date=_parse_date(row[0]),
                symbol=row[2].strip(),
                market=Market.JP,
                quantity=quantity,
                trade_currency=Currency.JPY,
                trade_amount=unit_price * abs(quantity),
                settlement_currency=Currency.JPY,
                settlement_amount=settlement_amount,
                account_type=_normalize_account_type(row[6]),
                position_group=request.position_group_jpy,
                settlement_group=request.settlement_group_jpy,
                source_file=file_name,
                source_line=line_number,
                memo=f"{row[1].strip()} / {row[3].strip()}",
            )
        )
    return items


def _parse_us_rows(
    rows: list[list[str]],
    request: BrokerImportPreviewRequest,
    file_name: str,
) -> list[BrokerImportPreviewItem]:
    start = _find_header_index(rows, "国内約定日") + 1
    items: list[BrokerImportPreviewItem] = []
    for line_number, row in enumerate(rows[start:], start=start + 1):
        if len(row) < 12 or not row[0].strip():
            continue
        trade_kind = row[6].strip()
        if "買" in trade_kind:
            quantity = float(row[8])
        elif "売" in trade_kind:
            quantity = -float(row[8])
        else:
            continue

        unit_price, trade_currency = _parse_unit_price(row[9])
        settlement_amount, settlement_currency = _parse_money(row[11])
        position_group = (
            request.position_group_jpy if settlement_currency == Currency.JPY else request.position_group_usd
        )
        settlement_group = (
            request.settlement_group_jpy if settlement_currency == Currency.JPY else request.settlement_group_usd
        )
        items.append(
            _build_item(
                trade_date=_parse_date(row[0]),
                symbol=row[2].strip(),
                market=Market.US,
                quantity=quantity,
                trade_currency=trade_currency,
                trade_amount=unit_price * abs(quantity),
                settlement_currency=settlement_currency,
                settlement_amount=settlement_amount,
                account_type=_normalize_account_type(row[7]),
                position_group=position_group,
                settlement_group=settlement_group,
                source_file=file_name,
                source_line=line_number,
                memo=f"{row[1].strip()} / {row[3].strip()}",
            )
        )
    return items


def preview_broker_import(request: BrokerImportPreviewRequest) -> BrokerImportPreviewResponse:
    items: list[BrokerImportPreviewItem] = []
    warnings: list[str] = []

    if request.domestic_report:
        try:
            items.extend(
                _parse_domestic_rows(
                    _reader_from_text(_decode_file(request.domestic_report)),
                    request,
                    request.domestic_report.file_name,
                )
            )
        except ValueError as exc:
            warnings.append(str(exc))

    if request.us_report:
        try:
            items.extend(
                _parse_us_rows(
                    _reader_from_text(_decode_file(request.us_report)),
                    request,
                    request.us_report.file_name,
                )
            )
        except ValueError as exc:
            warnings.append(str(exc))

    items.sort(
        key=lambda item: (
            item.trade_date,
            item.symbol,
            item.market.value,
            item.broker_account_type.value,
            0 if item.quantity > 0 else 1,
            item.source_line,
        )
    )
    return BrokerImportPreviewResponse(items=items, warnings=warnings)


def preview_items_to_transactions(items: Iterable[BrokerImportPreviewItem]) -> list[Transaction]:
    transactions: list[Transaction] = []
    for item in items:
        transactions.append(
            Transaction(
                id=item.transaction_id,
                trade_date=item.trade_date,
                symbol=item.symbol,
                quantity=item.quantity,
                gross_amount=item.settlement_amount,
                funding_group=item.position_group,
                cash_currency=item.settlement_currency,
                position_group=item.position_group,
                settlement_group=item.settlement_group,
                trade_currency=item.trade_currency,
                trade_amount=item.trade_amount,
                settlement_currency=item.settlement_currency,
                settlement_amount=item.settlement_amount,
                broker_account_type=item.broker_account_type,
                cross_currency=False,
                buy_currency=None,
                sell_currency=None,
                market=item.market,
                taxed=item.taxed,
                memo=item.memo,
            )
        )
    return transactions


def apply_broker_import(request: BrokerImportApplyRequest) -> BrokerImportPreviewResponse:
    return preview_broker_import(request)