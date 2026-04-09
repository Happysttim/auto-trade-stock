import { AlertTriangle, CheckCircle2, Info, ScrollText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { LogRecord } from "@/lib/types";

type LogsPanelProps = {
  logs: LogRecord[];
  loading: boolean;
};

function getLogIcon(eventType: string) {
  if (eventType === "error") {
    return AlertTriangle;
  }
  if (eventType === "order") {
    return CheckCircle2;
  }
  return Info;
}

function getBadgeVariant(level: string): "default" | "danger" | "outline" {
  if (level === "error") {
    return "danger";
  }
  if (level === "info") {
    return "default";
  }
  return "outline";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

export function LogsPanel({ logs, loading }: LogsPanelProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-primary/12 p-3 text-primary">
            <ScrollText className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>System Logs</CardTitle>
            <CardDescription>Signal analysis, proposal lifecycle, Kiwoom sync, and order errors</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? <p className="text-sm text-muted-foreground">Loading log stream...</p> : null}

        {!loading && logs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/80 p-5 text-sm text-muted-foreground">
            System logs will appear here when the scheduler starts writing events.
          </div>
        ) : null}

        {logs.map((log, index) => {
          const Icon = getLogIcon(log.event_type);
          return (
            <div key={log.id} className="space-y-4 rounded-2xl bg-background/60 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-3">
                  <div className="rounded-2xl bg-secondary p-2.5 text-muted-foreground">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-foreground">{log.message}</p>
                      <Badge variant={getBadgeVariant(log.level)}>{log.level}</Badge>
                    </div>
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{log.event_type}</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{formatDateTime(log.created_at)}</p>
              </div>

              {Object.keys(log.metadata ?? {}).length > 0 ? (
                <pre className="overflow-x-auto rounded-2xl bg-card px-4 py-3 text-xs leading-6 text-muted-foreground">
                  {JSON.stringify(log.metadata, null, 2)}
                </pre>
              ) : null}

              {index < logs.length - 1 ? <Separator /> : null}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
