import { Newspaper } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { SignalRecord } from "@/lib/types";

type SignalPanelProps = {
  signals: SignalRecord[];
  summary: string | null;
};

function signalVariant(type: SignalRecord["signal_type"]): "success" | "danger" | "outline" {
  if (type === "buy") {
    return "success";
  }
  if (type === "sell") {
    return "danger";
  }
  return "outline";
}

export function SignalPanel({ signals, summary }: SignalPanelProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-primary/12 p-3 text-primary">
            <Newspaper className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>AI Signal Feed</CardTitle>
            <CardDescription>News-driven scoring and recommendation history</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-2xl bg-background/70 p-4 text-sm leading-6 text-muted-foreground">
          {summary ?? "No AI summary has been stored yet."}
        </div>

        <div className="space-y-4">
          {signals.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/80 p-5 text-sm text-muted-foreground">
              Stored signals will appear here after the next completed news cycle.
            </div>
          ) : null}

          {signals.slice(0, 6).map((signal, index) => (
            <div key={signal.id} className="space-y-4 rounded-2xl bg-background/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-base font-semibold">{signal.company_name || signal.symbol}</p>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{signal.symbol}</p>
                </div>
                <Badge variant={signalVariant(signal.signal_type)}>{signal.signal_type}</Badge>
              </div>

              <div className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-muted-foreground">Score</p>
                  <p className="font-semibold">{signal.score} / 100</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Allocation</p>
                  <p className="font-semibold">{Math.round(signal.allocation_ratio * 100)}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Status</p>
                  <p className="font-semibold">{signal.execution_status}</p>
                </div>
              </div>

              <p className="text-sm leading-6 text-muted-foreground">{signal.rationale}</p>

              {index < Math.min(signals.length, 6) - 1 ? <Separator /> : null}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
