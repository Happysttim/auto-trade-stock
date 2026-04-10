import { ArrowDownRight, ArrowUpRight, Newspaper } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { SignalRecord } from "@/lib/types";

type SignalPanelProps = {
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

function signalTypeLabel(type: SignalRecord["signal_type"]): string {
  if (type === "buy") {
    return "매수";
  }
  if (type === "sell") {
    return "매도";
  }
  return "관망";
}

function executionStatusLabel(status: string): string {
  const labels: Record<string, string> = {
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
  };
  return labels[status] ?? status;
}

function actionButtonLabel(signal: SignalRecord): string {
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

function isActionDisabled(signal: SignalRecord, marketOpen: boolean, activeSignalId: number | null): boolean {
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

export function SignalPanel({ signals, summary, marketOpen, activeSignalId, onExecuteSignal }: SignalPanelProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-primary/12 p-3 text-primary">
            <Newspaper className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>AI 시그널</CardTitle>
            <CardDescription>뉴스 분석 점수와 추천 이력</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-2xl bg-background/70 p-4 text-sm leading-6 text-muted-foreground">
          {summary ?? "아직 저장된 AI 요약이 없습니다."}
        </div>

        <div className="space-y-4">
          {signals.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/80 p-5 text-sm text-muted-foreground">
              다음 뉴스 분석이 완료되면 저장된 시그널이 여기에 표시됩니다.
            </div>
          ) : null}

          {signals.slice(0, 6).map((signal, index) => (
            <div key={signal.id} className="space-y-4 rounded-2xl bg-background/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-base font-semibold">{signal.company_name || signal.symbol}</p>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{signal.symbol}</p>
                </div>
                {signal.signal_type === "hold" ? (
                  <Badge variant={signalVariant(signal.signal_type)}>{signalTypeLabel(signal.signal_type)}</Badge>
                ) : (
                  <Button
                    variant={signal.signal_type === "buy" ? "success" : "danger"}
                    disabled={isActionDisabled(signal, marketOpen, activeSignalId)}
                    onClick={async () => onExecuteSignal(signal.id)}
                  >
                    <span className="mr-2 inline-flex">
                      {signal.signal_type === "buy" ? (
                        <ArrowUpRight className="h-4 w-4" />
                      ) : (
                        <ArrowDownRight className="h-4 w-4" />
                      )}
                    </span>
                    {activeSignalId === signal.id ? "주문 전송 중..." : actionButtonLabel(signal)}
                  </Button>
                )}
              </div>

              <div className="grid gap-3 text-sm sm:grid-cols-4">
                <div>
                  <p className="text-muted-foreground">신호</p>
                  <p className="font-semibold">{signalTypeLabel(signal.signal_type)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">점수</p>
                  <p className="font-semibold">{signal.score} / 100</p>
                </div>
                <div>
                  <p className="text-muted-foreground">비중</p>
                  <p className="font-semibold">{Math.round(signal.allocation_ratio * 100)}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">상태</p>
                  <p className="font-semibold">{executionStatusLabel(signal.execution_status)}</p>
                </div>
              </div>

              <div className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-muted-foreground">핵심 키워드</p>
                  <p className="font-semibold">{signal.keyword}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">보유 예상 기간</p>
                  <p className="font-semibold">{signal.hold_days}일</p>
                </div>
                <div>
                  <p className="text-muted-foreground">거래량 비율</p>
                  <p className="font-semibold">{signal.volume_ratio.toFixed(2)}배</p>
                </div>
              </div>

              <p className="text-sm leading-6 text-muted-foreground">{signal.rationale}</p>

              {signal.suspicious_volume ? (
                <p className="text-xs text-danger">이상 거래량이 감지되어 직접 주문 버튼이 비활성화되었습니다.</p>
              ) : null}
              {!marketOpen && signal.signal_type !== "hold" ? (
                <p className="text-xs text-muted-foreground">장이 열려 있을 때만 시그널에서 바로 주문할 수 있습니다.</p>
              ) : null}

              {index < Math.min(signals.length, 6) - 1 ? <Separator /> : null}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
