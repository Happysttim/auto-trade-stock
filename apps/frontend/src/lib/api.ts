import type {
  DashboardData,
  HoldingRecord,
  KeywordAnalysisResult,
  LogRecord,
  OrderProposal,
  ServiceStatus,
  SignalRecord,
  TradeRecord,
} from "./types";

export type ManualTaskResult = {
  status: "ok";
  message: string;
  triggered_at: string;
  created_signals?: number;
  created_proposals?: number;
  holding_count?: number;
  cash_balance?: number;
  account_no?: string | null;
};

export type SignalExecutionResult = {
  status: "ok";
  message: string;
  proposal: OrderProposal;
};

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { message?: string; error?: string };
      if (payload.message) {
        message = payload.message;
      } else if (payload.error) {
        message = payload.error;
      }
    } catch {}
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchDashboardData(): Promise<DashboardData> {
  const [status, proposals, holdings, trades, logs, signals] = await Promise.all([
    fetchJson<ServiceStatus>("/api/status"),
    fetchJson<OrderProposal[]>("/api/proposals?limit=100"),
    fetchJson<HoldingRecord[]>("/api/holdings?limit=100"),
    fetchJson<TradeRecord[]>("/api/trades?limit=50"),
    fetchJson<LogRecord[]>("/api/logs?limit=120"),
    fetchJson<SignalRecord[]>("/api/signals?limit=20"),
  ]);

  return {
    status,
    proposals,
    holdings,
    trades,
    logs,
    signals,
  };
}

export async function approveProposal(proposalId: number): Promise<OrderProposal> {
  const payload = await fetchJson<{ proposal: OrderProposal }>(`/api/proposals/${proposalId}/approve`, {
    method: "POST",
  });
  return payload.proposal;
}

export async function rejectProposal(proposalId: number): Promise<OrderProposal> {
  const payload = await fetchJson<{ proposal: OrderProposal }>(`/api/proposals/${proposalId}/reject`, {
    method: "POST",
  });
  return payload.proposal;
}

export async function executeSignal(signalId: number): Promise<SignalExecutionResult> {
  return fetchJson<SignalExecutionResult>(`/api/signals/${signalId}/execute`, {
    method: "POST",
  });
}

type LegacyScanNewsResult = {
  status: string;
  created_signals?: number;
  message?: string;
  triggered_at?: string;
};

type LegacyRunCycleResult = {
  status: string;
  triggered_at?: string;
};

export function runManualAnalysis(): Promise<ManualTaskResult> {
  return fetchJson<ManualTaskResult>("/api/tasks/run-analysis", {
    method: "POST",
  }).catch(async (error: unknown) => {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }

    const holdings = await syncHoldingsNow();
    const scan = await fetchJson<LegacyScanNewsResult>("/api/tasks/scan-news", {
      method: "POST",
    });
    const cycle = await fetchJson<LegacyRunCycleResult>("/api/tasks/run-cycle", {
      method: "POST",
    });

    return {
      status: "ok",
      triggered_at: cycle.triggered_at ?? scan.triggered_at ?? new Date().toISOString(),
      created_signals: scan.created_signals ?? 0,
      holding_count: holdings.holding_count,
      account_no: holdings.account_no ?? null,
      message:
        scan.message ??
        `호환 모드로 수동 분석을 완료했습니다. 보유 종목 ${holdings.holding_count ?? 0}개를 동기화하고 기존 뉴스/제안 사이클을 실행했습니다.`,
    };
  });
}

export async function buildProposalsNow(): Promise<ManualTaskResult> {
  try {
    return await fetchJson<ManualTaskResult>("/api/tasks/build-proposals", {
      method: "POST",
    });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }

    const result = await fetchJson<LegacyRunCycleResult>("/api/tasks/run-cycle", {
      method: "POST",
    });
    return {
      status: "ok",
      triggered_at: result.triggered_at ?? new Date().toISOString(),
      message: "호환 모드에서 기존 run-cycle 경로를 사용해 주문 제안 생성을 실행했습니다.",
    };
  }
}

export function syncHoldingsNow(): Promise<ManualTaskResult> {
  return fetchJson<ManualTaskResult>("/api/tasks/sync-holdings", {
    method: "POST",
  });
}

export function runKeywordAnalysis(keyword: string): Promise<KeywordAnalysisResult> {
  return fetchJson<KeywordAnalysisResult>("/api/analysis/keyword", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ keyword }),
  });
}
