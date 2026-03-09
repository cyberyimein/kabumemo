export type Market = "JP" | "US";
export type Currency = "JPY" | "USD";
export type TaxStatus = "Y" | "N";
export type BrokerAccountType = "NISA" | "SPECIFIC" | "GENERAL" | "UNKNOWN";

export interface FundingGroup {
  name: string;
  currency: Currency;
  initial_amount: number;
  notes?: string | null;
}

export interface FundingGroupUpdate {
  currency?: Currency;
  initial_amount?: number;
  notes?: string | null;
}

export interface FundingCapitalAdjustmentPayload {
  amount: number;
  effective_date: string;
  notes?: string | null;
}

export interface FundingCapitalAdjustmentRequest extends FundingCapitalAdjustmentPayload {
  funding_group: string;
}

export interface FundingCapitalAdjustment extends FundingCapitalAdjustmentPayload {
  id: string;
  funding_group: string;
}

export interface StockSplitPayload {
  symbol: string;
  market: Market;
  effective_date: string;
  ratio_before: number;
  ratio_after: number;
  notes?: string | null;
}

export interface StockSplit extends StockSplitPayload {
  id: string;
}

export interface FxExchangeBase {
  exchange_date: string;
  from_currency: Currency;
  to_currency: Currency;
  from_amount: number;
  to_amount?: number;
  rate?: number;
  notes?: string | null;
  transaction_id?: string | null;
}

export type FxExchangeCreate = FxExchangeBase;

export interface FxExchangeRecord extends FxExchangeBase {
  id: string;
  to_amount: number;
  rate: number;
}

export interface TransactionBase {
  trade_date: string;
  symbol: string;
  quantity: number;
  gross_amount: number;
  funding_group: string;
  cash_currency: Currency;
  position_group?: string | null;
  settlement_group?: string | null;
  trade_currency?: Currency | null;
  trade_amount?: number | null;
  settlement_currency?: Currency | null;
  settlement_amount?: number | null;
  broker_account_type?: BrokerAccountType;
  cross_currency: boolean;
  buy_currency?: Currency | null;
  sell_currency?: Currency | null;
  market: Market;
  taxed: TaxStatus;
  memo?: string | null;
}

export interface TransactionCreate extends Omit<TransactionBase, "taxed"> {
  taxed?: TaxStatus;
}

export type TransactionUpdate = TransactionBase;

export interface Transaction extends TransactionBase {
  id: string;
}

export interface RoundTripYieldRequest {
  transaction_ids: string[];
}

export interface RoundTripYieldResponse {
  symbol: string;
  funding_group: string;
  market: Market;
  cash_currency: Currency;
  transaction_ids: string[];
  trade_count: number;
  total_buy_quantity: number;
  total_sell_quantity: number;
  total_buy_amount: number;
  total_sell_amount: number;
  gross_profit: number;
  tax_total: number;
  net_profit: number;
  return_ratio: number | null;
  return_after_tax: number | null;
  annualized_return: number | null;
  annualized_return_after_tax: number | null;
  holding_days: number;
  trade_window_start: string;
  trade_window_end: string;
}

export interface PositionBreakdown {
  currency: Currency;
  quantity: number;
  average_cost: number;
  realized_pl: number;
  current_price?: number | null;
  unrealized_pl?: number | null;
}

export interface PositionGroupBreakdown {
  funding_group: string;
  currency: Currency;
  quantity: number;
  average_cost: number;
  realized_pl: number;
  current_price?: number | null;
  unrealized_pl?: number | null;
}

export interface Position {
  symbol: string;
  market: Market;
  breakdown: PositionBreakdown[];
  group_breakdown: PositionGroupBreakdown[];
}

export interface QuoteRecord {
  symbol: string;
  market: Market;
  price: number;
  currency: Currency;
  as_of: string;
}

export interface QuoteSnapshot {
  as_of: string;
  records: QuoteRecord[];
}

export type TradeSide = "buy" | "sell";

export interface PriceHistoryPoint {
  date: string;
  close: number;
}

export interface TradeMarker {
  date: string;
  price: number;
  side: TradeSide;
  quantity: number;
  currency: Currency;
  transaction_id: string;
}

export interface PositionHistoryResponse {
  symbol: string;
  market: Market;
  currency: Currency;
  series: PriceHistoryPoint[];
  markers: TradeMarker[];
}

export interface FundSnapshot {
  name: string;
  currency: Currency;
  initial_amount: number;
  cash_balance: number;
  holding_cost: number;
  current_total: number;
  total_pl: number;
  current_year_pl: number;
  current_year_pl_ratio: number | null;
  previous_year_pl: number;
  previous_year_pl_ratio: number | null;
}

export interface AggregatedFundSnapshot {
  currency: Currency;
  group_count: number;
  initial_amount: number;
  cash_balance: number;
  holding_cost: number;
  current_total: number;
  total_pl: number;
  current_year_pl: number;
  current_year_pl_ratio: number | null;
  previous_year_pl: number;
  previous_year_pl_ratio: number | null;
}

export interface FundSnapshotsResponse {
  funds: FundSnapshot[];
  aggregated: AggregatedFundSnapshot[];
}

export interface TaxSettlementRequest {
  transaction_id: string;
  funding_group: string;
  amount: number;
  currency: Currency;
  exchange_rate?: number;
  balance_exchange_rate?: number;
}

export interface TaxSettlementRecord {
  id: string;
  transaction_id: string;
  funding_group: string;
  amount: number;
  currency: Currency;
  exchange_rate?: number | null;
  jpy_equivalent: number;
  balance_exchange_rate?: number | null;
  balance_usd_required?: number | null;
  recorded_at: string;
}

export interface TaxSettlementUpdate {
  amount?: number;
  funding_group?: string;
  exchange_rate?: number;
  balance_exchange_rate?: number;
}

export interface AnnualTaxSettlement {
  id: string;
  year: number;
  funding_group: string;
  amount: number;
  currency: Currency;
  notes?: string | null;
  recorded_at: string;
}

export interface AnnualTaxSettlementCreate {
  year: number;
  funding_group: string;
  amount: number;
  currency: Currency;
  notes?: string | null;
  recorded_at?: string;
}

export interface AnnualTaxSettlementUpdate {
  year?: number;
  funding_group?: string;
  amount?: number;
  currency?: Currency;
  notes?: string | null;
  recorded_at?: string;
}

export interface BrokerImportFile {
  file_name: string;
  content_base64: string;
  encoding_hint?: string | null;
}

export interface BrokerImportPreviewRequest {
  domestic_report?: BrokerImportFile | null;
  us_report?: BrokerImportFile | null;
  position_group_jpy?: string;
  settlement_group_jpy?: string;
  position_group_usd?: string;
  settlement_group_usd?: string;
}

export interface BrokerImportPreviewItem {
  trade_date: string;
  symbol: string;
  market: Market;
  quantity: number;
  trade_currency: Currency;
  trade_amount: number;
  settlement_currency: Currency;
  settlement_amount: number;
  broker_account_type: BrokerAccountType;
  position_group: string;
  settlement_group: string;
  source_file: string;
  source_line: number;
  transaction_id: string;
  taxed: TaxStatus;
  memo?: string | null;
}

export interface BrokerImportPreviewResponse {
  items: BrokerImportPreviewItem[];
  warnings: string[];
  applied_count: number;
  skipped_count: number;
}

export interface BrokerImportApplyRequest extends BrokerImportPreviewRequest {
  replace_existing_transactions?: boolean;
}

export interface HealthResponse {
  status: string;
}
