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

export interface PositionBreakdown {
  currency: Currency;
  quantity: number;
  average_cost: number;
  realized_pl: number;
}

export interface Position {
  symbol: string;
  market: Market;
  breakdown: PositionBreakdown[];
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
