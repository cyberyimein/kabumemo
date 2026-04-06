import type {
  AnnualTaxSettlement,
  AnnualTaxSettlementCreate,
  AnnualTaxSettlementUpdate,
  BatchDeleteTransactionsRequest,
  BatchDeleteTransactionsResponse,
  BrokerImportApplyRequest,
  BrokerImportPreviewResponse,
  BrokerImportPreviewRequest,
  FxExchangeCreate,
  FxExchangeRecord,
  FundSnapshotsResponse,
  FundingCapitalAdjustment,
  FundingCapitalAdjustmentRequest,
  FundingGroup,
  FundingGroupUpdate,
  HealthResponse,
  Position,
  PositionHistoryResponse,
  QuoteSnapshot,
  RoundTripYieldRequest,
  RoundTripYieldResponse,
  StockSplit,
  StockSplitPayload,
  SuspiciousDuplicateResponse,
  TaxSettlementRecord,
  TaxSettlementRequest,
  TaxSettlementUpdate,
  Transaction,
  TransactionCreate,
  TransactionUpdate
} from "@/types/api";

const API_BASE = "/api";

class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    const detail = await safeParseError(response);
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function safeParseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string"
      ? payload.detail
      : JSON.stringify(payload);
  } catch {
    return response.statusText || "请求失败";
  }
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

// Transactions -------------------------------------------------------------------
export function getTransactions(): Promise<Transaction[]> {
  return request<Transaction[]>("/transactions");
}

export function createTransaction(payload: TransactionCreate): Promise<Transaction> {
  return request<Transaction>("/transactions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateTransaction(
  id: string,
  payload: TransactionUpdate
): Promise<Transaction> {
  return request<Transaction>(`/transactions/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteTransaction(id: string): Promise<void> {
  return request<void>(`/transactions/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export function getSuspiciousDuplicateTransactions(): Promise<SuspiciousDuplicateResponse> {
  return request<SuspiciousDuplicateResponse>("/transactions/suspicious-duplicates");
}

export function deleteTransactionsBatch(
  payload: BatchDeleteTransactionsRequest
): Promise<BatchDeleteTransactionsResponse> {
  return request<BatchDeleteTransactionsResponse>("/transactions/batch-delete", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function calculateRoundYield(
  payload: RoundTripYieldRequest
): Promise<RoundTripYieldResponse> {
  return request<RoundTripYieldResponse>("/transactions/round-yield", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

// Positions ----------------------------------------------------------------------
export function getPositions(): Promise<Position[]> {
  return request<Position[]>("/positions");
}

export function getPositionHistory(
  symbol: string,
  market: string,
  period = "1y"
): Promise<PositionHistoryResponse> {
  const params = new URLSearchParams({ symbol, market, period });
  return request<PositionHistoryResponse>(`/positions/history?${params.toString()}`);
}

// Quotes ------------------------------------------------------------------------
export function getQuotes(): Promise<QuoteSnapshot> {
  return request<QuoteSnapshot>("/quotes");
}

export function refreshQuotes(force = false): Promise<QuoteSnapshot> {
  const suffix = force ? "?force=true" : "";
  return request<QuoteSnapshot>(`/quotes/refresh${suffix}`, {
    method: "POST"
  });
}

export async function getUsdJpyRate(): Promise<number> {
  const response = await fetch("https://api.frankfurter.app/latest?from=USD&to=JPY");

  if (!response.ok) {
    throw new ApiError(response.statusText || "Unable to fetch exchange rate", response.status);
  }

  const payload = (await response.json()) as { rates?: { JPY?: number } };
  const rate = payload.rates?.JPY;

  if (typeof rate !== "number" || !Number.isFinite(rate) || rate <= 0) {
    throw new ApiError("Invalid USD/JPY exchange rate response", 502);
  }

  return rate;
}

// Funds --------------------------------------------------------------------------
export function getFunds(): Promise<FundSnapshotsResponse> {
  return request<FundSnapshotsResponse>("/funds");
}

// Funding groups -----------------------------------------------------------------
export function getFundingGroups(): Promise<FundingGroup[]> {
  return request<FundingGroup[]>("/funding-groups");
}

export function createFundingGroup(payload: FundingGroup): Promise<FundingGroup> {
  return request<FundingGroup>("/funding-groups", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateFundingGroup(
  name: string,
  payload: FundingGroupUpdate
): Promise<FundingGroup> {
  return request<FundingGroup>(`/funding-groups/${encodeURIComponent(name)}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteFundingGroup(name: string): Promise<void> {
  return request<void>(`/funding-groups/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
}

export function addFundingCapital(
  payload: FundingCapitalAdjustmentRequest
): Promise<FundingCapitalAdjustment> {
  const { funding_group, ...body } = payload;
  return request<FundingCapitalAdjustment>(
    `/funding-groups/${encodeURIComponent(funding_group)}/capital`,
    {
      method: "POST",
      body: JSON.stringify(body)
    }
  );
}

export function getCapitalAdjustments(): Promise<FundingCapitalAdjustment[]> {
  return request<FundingCapitalAdjustment[]>("/funding-groups/capital");
}

export function getStockSplits(): Promise<StockSplit[]> {
  return request<StockSplit[]>("/stock-splits").catch((error: unknown) => {
    if (error instanceof ApiError && error.status === 404) {
      return [];
    }
    throw error;
  });
}

export function createStockSplit(payload: StockSplitPayload): Promise<StockSplit> {
  return request<StockSplit>("/stock-splits", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function deleteStockSplit(id: string): Promise<void> {
  return request<void>(`/stock-splits/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

// FX exchanges -----------------------------------------------------------------
export function getFxExchanges(): Promise<FxExchangeRecord[]> {
  return request<FxExchangeRecord[]>("/fx-exchanges");
}

export function createFxExchange(payload: FxExchangeCreate): Promise<FxExchangeRecord> {
  return request<FxExchangeRecord>("/fx-exchanges", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function deleteFxExchange(id: string): Promise<void> {
  return request<void>(`/fx-exchanges/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

// Tax settlements ----------------------------------------------------------------
export function settleTax(payload: TaxSettlementRequest): Promise<TaxSettlementRecord> {
  return request<TaxSettlementRecord>("/tax/settlements", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getTaxSettlements(): Promise<TaxSettlementRecord[]> {
  return request<TaxSettlementRecord[]>("/tax/settlements");
}

export function updateTaxSettlement(
  id: string,
  payload: TaxSettlementUpdate
): Promise<TaxSettlementRecord> {
  return request<TaxSettlementRecord>(`/tax/settlements/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteTaxSettlement(id: string): Promise<void> {
  return request<void>(`/tax/settlements/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export function getAnnualTaxSettlements(): Promise<AnnualTaxSettlement[]> {
  return request<AnnualTaxSettlement[]>("/tax/annual");
}

export function createAnnualTaxSettlement(
  payload: AnnualTaxSettlementCreate
): Promise<AnnualTaxSettlement> {
  return request<AnnualTaxSettlement>("/tax/annual", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAnnualTaxSettlement(
  id: string,
  payload: AnnualTaxSettlementUpdate
): Promise<AnnualTaxSettlement> {
  return request<AnnualTaxSettlement>(`/tax/annual/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteAnnualTaxSettlement(id: string): Promise<void> {
  return request<void>(`/tax/annual/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export function previewBrokerImport(
  payload: BrokerImportPreviewRequest
): Promise<BrokerImportPreviewResponse> {
  return request<BrokerImportPreviewResponse>("/imports/broker/preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function applyBrokerImport(
  payload: BrokerImportApplyRequest
): Promise<BrokerImportPreviewResponse> {
  return request<BrokerImportPreviewResponse>("/imports/broker/apply", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export { ApiError };
