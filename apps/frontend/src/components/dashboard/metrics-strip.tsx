import { Clock3, Database, Landmark, Wallet } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { DashboardData } from "@/lib/types";

type MetricsStripProps = {
  data: DashboardData | null;
  loading: boolean;
};

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "데이터 없음";
  }
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

const metricDefinitions = [
  {
    key: "market",
    title: "장 상태",
    icon: Landmark,
    getValue: (data: DashboardData | null) => (data?.status.market_open ? "열림" : "닫힘"),
    getDescription: (data: DashboardData | null) =>
      data?.status.operating_window ? "AI 분석 가능 시간" : "운영 시간 외",
  },
  {
    key: "signals",
    title: "시그널 수",
    icon: Database,
    getValue: (data: DashboardData | null) => String(data?.status.latest_signal_count ?? 0),
    getDescription: () => "SQLite에 저장된 최신 AI 시그널",
  },
  {
    key: "approvals",
    title: "승인 대기",
    icon: Wallet,
    getValue: (data: DashboardData | null) => String(data?.status.pending_proposal_count ?? 0),
    getDescription: () => "사용자 확인을 기다리는 주문",
  },
  {
    key: "cycle",
    title: "보유 종목 동기화",
    icon: Clock3,
    getValue: (data: DashboardData | null) => formatDateTime(data?.status.last_holdings_sync_at),
    getDescription: (data: DashboardData | null) =>
      data?.status.active_account_no ? `계좌 ${data.status.active_account_no}` : "동기화된 키움 계좌 없음",
  },
];

export function MetricsStrip({ data, loading }: MetricsStripProps) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {metricDefinitions.map((metric) => {
        const Icon = metric.icon;
        return (
          <Card key={metric.key}>
            <CardContent className="flex items-start gap-4 p-5">
              <div className="rounded-2xl bg-primary/12 p-3 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <div className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  {metric.title}
                </p>
                <p className="text-xl font-semibold text-foreground">
                  {loading ? "불러오는 중..." : metric.getValue(data)}
                </p>
                <p className="text-sm text-muted-foreground">{metric.getDescription(data)}</p>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </section>
  );
}
