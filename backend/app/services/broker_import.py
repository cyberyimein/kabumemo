from __future__ import annotations

import base64
import csv
import hashlib
import io
from datetime import date, datetime
from typing import Iterable

from ..models.schemas import (
    BrokerAccountType,
    BrokerImportApplyRequest,
    BrokerImportFile,
    BrokerImportPreviewItem,
    BrokerImportPreviewRequest,
    BrokerImportPreviewResponse,
    CashActivity,
    CashActivityCategory,
    CashDirection,
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


def _cash_activity_id(*parts: str) -> str:
    return _stable_transaction_id(parts)


def _cash_category(detail: str, kind: str, *, foreign: bool) -> CashActivityCategory:
    if "入出金振替" in detail or "保証金" in detail:
        return CashActivityCategory.INTERNAL_TRANSFER
    if "米国株式買付代金" in detail or "米国株式売却代金" in detail:
        return CashActivityCategory.INTERNAL_TRANSFER
    if "税" in detail:
        return CashActivityCategory.TAX
    if "配当" in kind or "分配" in kind or "配当" in detail:
        return CashActivityCategory.DIVIDEND
    if "外国為替取引" in detail:
        return CashActivityCategory.FX
    if "投信" in detail:
        return CashActivityCategory.INVESTMENT
    if "銀行" in detail or "金融機関" in kind or "外貨入金" in detail or "外貨出金" in detail:
        return CashActivityCategory.EXTERNAL_TRANSFER
    return CashActivityCategory.OTHER


def _parse_cash_rows(
    rows: list[list[str]], file_name: str, *, foreign: bool
) -> list[CashActivity]:
    start = _find_header_index(rows, "入出金日")
    header = [cell.strip() for cell in rows[start]]
    index = {name: position for position, name in enumerate(header)}
    required = {"入出金日", "取引", "区分", "摘要", "出金額", "入金額"}
    if not required.issubset(index):
        raise ValueError("Cash report columns are incomplete")

    items: list[CashActivity] = []
    occurrences: dict[tuple[str, ...], int] = {}
    for line_number, row in enumerate(rows[start + 1 :], start=start + 2):
        if not row or not row[0].strip():
            continue
        direction = CashDirection.IN if row[index["取引"]].strip() == "入金" else CashDirection.OUT
        amount_index = index["入金額"] if direction == CashDirection.IN else index["出金額"]
        amount = float((row[amount_index] or "0").replace(",", "").strip())
        detail_type = row[index["区分"]].strip()
        description = row[index["摘要"]].strip()
        raw_currency = row[index["通貨"]].strip() if "通貨" in index else "円"
        currency = Currency.USD if raw_currency == "米ドル" else (None if raw_currency == "-" else Currency.JPY)
        activity_date = _parse_date(row[index["入出金日"]])
        fingerprint = (
            activity_date.isoformat(), direction.value, currency.value if currency else "-",
            f"{amount:.4f}", detail_type, description,
        )
        occurrence = occurrences.get(fingerprint, 0) + 1
        occurrences[fingerprint] = occurrence
        activity_id = _cash_activity_id(*fingerprint, str(occurrence))
        items.append(
            CashActivity(
                id=activity_id,
                activity_date=activity_date,
                direction=direction,
                currency=currency,
                amount=round(amount, 4),
                category=_cash_category(description, detail_type, foreign=foreign),
                transaction_type=row[index["取引"]].strip(),
                detail_type=detail_type,
                description=description,
                source_file=file_name,
                source_line=line_number,
            )
        )
    return items


def _link_cash_transfers(items: list[CashActivity]) -> None:
    jpy_candidates = [
        item for item in items
        if item.currency == Currency.JPY
        and item.description in {"米国株式買付代金", "米国株式売却代金"}
    ]
    foreign_candidates = [
        item for item in items if item.currency is None and item.description == "入出金振替"
    ]
    used: set[str] = set()
    for jpy_item in jpy_candidates:
        counterpart = next(
            (
                item for item in foreign_candidates
                if item.id not in used
                and item.activity_date == jpy_item.activity_date
                and abs(item.amount - jpy_item.amount) < 0.005
                and item.direction != jpy_item.direction
            ),
            None,
        )
        if counterpart is None:
            continue
        used.add(counterpart.id)
        link_id = _cash_activity_id(
            "cash-link", jpy_item.activity_date.isoformat(), f"{jpy_item.amount:.2f}", jpy_item.id, counterpart.id
        )
        jpy_item.link_group_id = link_id
        counterpart.link_group_id = link_id
        jpy_item.linked_activity_id = counterpart.id
        counterpart.linked_activity_id = jpy_item.id


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
    cash_items: list[CashActivity] = []
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

    for report, foreign in (
        (request.jpy_cash_report, False),
        (request.foreign_cash_report, True),
    ):
        if not report:
            continue
        try:
            cash_items.extend(
                _parse_cash_rows(_reader_from_text(_decode_file(report)), report.file_name, foreign=foreign)
            )
        except ValueError as exc:
            warnings.append(str(exc))

    _link_cash_transfers(cash_items)
    cash_items.sort(key=lambda item: (item.activity_date, item.source_file, item.source_line), reverse=True)

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
    return BrokerImportPreviewResponse(items=items, cash_items=cash_items, warnings=warnings)


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
