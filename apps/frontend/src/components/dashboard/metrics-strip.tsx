import { Clock3, Database, Landmark, Wallet } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { DashboardData } from "@/lib/types";

type MetricsStripProps = {
  data: DashboardData | null;
  loading: boolean;
};

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "No data";
  }
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

const metricDefinitions = [
  {
    key: "market",
    title: "Market",
    icon: Landmark,
    getValue: (data: DashboardData | null) => (data?.status.market_open ? "Open" : "Closed"),
    getDescription: (data: DashboardData | null) =>
      data?.status.operating_window ? "AI working window active" : "Outside working window",
  },
  {
    key: "signals",
    title: "Signals",
    icon: Database,
    getValue: (data: DashboardData | null) => String(data?.status.latest_signal_count ?? 0),
    getDescription: () => "Latest AI signals stored in SQLite",
  },
  {
    key: "approvals",
    title: "Pending Approval",
    icon: Wallet,
    getValue: (data: DashboardData | null) => String(data?.status.pending_proposal_count ?? 0),
    getDescription: () => "Orders waiting for user confirmation",
  },
  {
    key: "cycle",
    title: "Holdings Sync",
    icon: Clock3,
    getValue: (data: DashboardData | null) => formatDateTime(data?.status.last_holdings_sync_at),
    getDescription: (data: DashboardData | null) =>
      data?.status.active_account_no ? `Account ${data.status.active_account_no}` : "No Kiwoom account synced",
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
                  {loading ? "Loading..." : metric.getValue(data)}
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
