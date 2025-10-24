import type {
  FundSnapshot,
  FundSnapshotsResponse,
  FundingGroup,
  FundingGroupUpdate,
  HealthResponse,
  Position,
  RoundTripYieldRequest,
  RoundTripYieldResponse,
  TaxSettlementRequest,
  TaxSettlementRecord,
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
  } catch (err) {
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

export { ApiError };
