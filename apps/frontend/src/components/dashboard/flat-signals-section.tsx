import { ArrowDownRight, ArrowUpRight, Newspaper } from "lucide-react";

import { SectionShell } from "@/components/dashboard/section-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SignalRecord } from "@/lib/types";

type FlatSignalsSectionProps = {
  signals: SignalRecord[];
  summary: string | null;
  marketOpen: boolean;
  activeSignalId: number | null;
  onExecuteSignal: (signalId: number) => Promise<void>;
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

function signalTypeLabel(type: SignalRecord["signal_type"]) {
  if (type === "buy") {
    return "매수";
  }
  if (type === "sell") {
    return "매도";
  }
  return "관망";
}

function executionStatusLabel(status: string) {
  return (
    {
      pending: "대기",
      proposed: "승인 대기",
      executed: "주문 완료",
      failed: "실패",
      rejected: "거절",
      ignored: "관망 처리",
      blocked: "차단",
      skipped: "조건 미달",
      "not-held": "미보유",
      "unsupported-symbol": "주문 불가",
    }[status] ?? status
  );
}

function actionButtonLabel(signal: SignalRecord) {
  if (signal.signal_type === "buy") {
    if (signal.execution_status === "executed") {
      return "매수 완료";
    }
    if (signal.execution_status === "proposed") {
      return "승인 대기";
    }
    return "매수 실행";
  }
  if (signal.signal_type === "sell") {
    if (signal.execution_status === "executed") {
      return "매도 완료";
    }
    if (signal.execution_status === "proposed") {
      return "승인 대기";
    }
    return "매도 실행";
  }
  return "관망";
}

function isActionDisabled(signal: SignalRecord, marketOpen: boolean, activeSignalId: number | null) {
  if (signal.signal_type === "hold") {
    return true;
  }
  if (!marketOpen || signal.suspicious_volume) {
    return true;
  }
  if (signal.execution_status === "proposed" || signal.execution_status === "executed") {
    return true;
  }
  return activeSignalId !== null && activeSignalId !== signal.id;
}

export function FlatSignalsSection({
  signals,
  summary,
  marketOpen,
  activeSignalId,
  onExecuteSignal,
}: FlatSignalsSectionProps) {
  return (
    <SectionShell eyebrow="Signals" title="AI 시그널" description="정규 뉴스 분석에서 저장된 최신 시그널입니다.">
      <div className="rounded-2xl bg-muted/55 px-4 py-4 text-sm leading-7 text-muted-foreground">
        <div className="mb-2 flex items-center gap-2 font-medium text-foreground">
          <Newspaper className="h-4 w-4 text-primary" />
          AI 요약
        </div>
        {summary ?? "아직 저장된 AI 요약이 없습니다."}
      </div>

      <div className="mt-4 space-y-3">
        {signals.length === 0 ? (
          <div className="rounded-2xl bg-muted/50 px-4 py-5 text-sm text-muted-foreground">
            표시할 시그널이 없습니다.
          </div>
        ) : null}

        {signals.map((signal) => (
          <div key={signal.id} className="rounded-2xl bg-background/55 px-4 py-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-base font-semibold text-foreground">{signal.company_name || signal.symbol}</p>
                    <Badge variant={signalVariant(signal.signal_type)}>{signalTypeLabel(signal.signal_type)}</Badge>
                    <Badge variant="outline">{executionStatusLabel(signal.execution_status)}</Badge>
                  </div>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">{signal.symbol}</p>
                </div>

                <div className="grid gap-3 text-sm sm:grid-cols-4">
                  <div>
                    <p className="text-muted-foreground">점수</p>
                    <p className="font-semibold text-foreground">{signal.score} / 100</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">키워드</p>
                    <p className="font-semibold text-foreground">{signal.keyword}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">비중</p>
                    <p className="font-semibold text-foreground">{Math.round(signal.allocation_ratio * 100)}%</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">보유 기간</p>
                    <p className="font-semibold text-foreground">{signal.hold_days}일</p>
                  </div>
                </div>

                <p className="text-sm leading-6 text-muted-foreground">{signal.rationale}</p>

                {signal.suspicious_volume ? (
                  <p className="text-xs text-danger">이상 거래량이 감지되어 직접 실행이 잠겨 있습니다.</p>
                ) : null}
                {!marketOpen && signal.signal_type !== "hold" ? (
                  <p className="text-xs text-muted-foreground">시장 개장 중에만 시그널 즉시 실행이 가능합니다.</p>
                ) : null}
              </div>

              {signal.signal_type === "hold" ? null : (
                <Button
                  variant={signal.signal_type === "buy" ? "success" : "danger"}
                  disabled={isActionDisabled(signal, marketOpen, activeSignalId)}
                  onClick={async () => onExecuteSignal(signal.id)}
                >
                  {signal.signal_type === "buy" ? (
                    <ArrowUpRight className="mr-2 h-4 w-4" />
                  ) : (
                    <ArrowDownRight className="mr-2 h-4 w-4" />
                  )}
                  {activeSignalId === signal.id ? "주문 전송 중..." : actionButtonLabel(signal)}
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </SectionShell>
  );
}
