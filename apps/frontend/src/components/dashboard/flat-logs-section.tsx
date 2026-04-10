import { AlertTriangle, CheckCircle2, Info } from "lucide-react";

import { SectionShell } from "@/components/dashboard/section-shell";
import { Badge } from "@/components/ui/badge";
import type { LogRecord } from "@/lib/types";

type FlatLogsSectionProps = {
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

export function FlatLogsSection({ logs, loading }: FlatLogsSectionProps) {
  return (
    <SectionShell eyebrow="Logs" title="시스템 로그" description="분석, 주문 제안, 주문 처리, 오류가 시간순으로 기록됩니다.">
      <div className="space-y-3">
        {loading ? <p className="text-sm text-muted-foreground">로그를 불러오는 중입니다...</p> : null}

        {!loading && logs.length === 0 ? (
          <div className="rounded-2xl bg-muted/50 px-4 py-5 text-sm text-muted-foreground">
            아직 기록된 시스템 로그가 없습니다.
          </div>
        ) : null}

        {logs.map((log) => {
          const Icon = getLogIcon(log.event_type);
          return (
            <div key={log.id} className="rounded-2xl bg-background/55 px-4 py-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-3">
                  <div className="rounded-2xl bg-secondary p-2.5 text-muted-foreground">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-foreground">{log.message}</p>
                      <Badge variant={getBadgeVariant(log.level)}>
                        {log.level === "error" ? "오류" : log.level === "info" ? "정보" : log.level}
                      </Badge>
                    </div>
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{log.event_type}</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{formatDateTime(log.created_at)}</p>
              </div>

              {Object.keys(log.metadata ?? {}).length > 0 ? (
                <pre className="mt-3 overflow-x-auto rounded-2xl bg-muted/60 px-4 py-3 text-xs leading-6 text-muted-foreground">
                  {JSON.stringify(log.metadata, null, 2)}
                </pre>
              ) : null}
            </div>
          );
        })}
      </div>
    </SectionShell>
  );
}
