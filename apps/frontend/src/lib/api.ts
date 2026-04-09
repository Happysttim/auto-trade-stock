import type {
  DashboardData,
  HoldingRecord,
  LogRecord,
  OrderProposal,
  ServiceStatus,
  SignalRecord,
  TradeRecord,
} from "./types";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { message?: string };
      if (payload.message) {
        message = payload.message;
      }
    } catch {}
    throw new Error(message);
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
