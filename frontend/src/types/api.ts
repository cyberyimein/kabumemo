export type Market = "JP" | "US";
export type Currency = "JPY" | "USD";
export type TaxStatus = "Y" | "N";

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

export interface TransactionBase {
  trade_date: string;
  symbol: string;
  quantity: number;
  gross_amount: number;
  funding_group: string;
  cash_currency: Currency;
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
}

export interface PositionGroupBreakdown {
  funding_group: string;
  currency: Currency;
  quantity: number;
  average_cost: number;
  realized_pl: number;
}

export interface Position {
  symbol: string;
  market: Market;
  breakdown: PositionBreakdown[];
  group_breakdown: PositionGroupBreakdown[];
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
}

export interface TaxSettlementRecord {
  id: string;
  transaction_id: string;
  funding_group: string;
  amount: number;
  currency: Currency;
  exchange_rate?: number | null;
  jpy_equivalent: number;
  recorded_at: string;
}

export interface TaxSettlementUpdate {
  amount?: number;
  funding_group?: string;
  exchange_rate?: number;
}

export interface HealthResponse {
  status: string;
}
