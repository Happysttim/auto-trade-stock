import { useEffect, useState } from "react";
import { Activity, ListChecks, RefreshCcw, ShieldCheck, Sparkles, Wallet } from "lucide-react";

import { HoldingsPanel } from "@/components/dashboard/holdings-panel";
import { LogsPanel } from "@/components/dashboard/logs-panel";
import { MetricsStrip } from "@/components/dashboard/metrics-strip";
import { ProposalsTable } from "@/components/dashboard/proposals-table";
import { SignalPanel } from "@/components/dashboard/signal-panel";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { TradesTable } from "@/components/dashboard/trades-table";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  approveProposal,
  executeSignal,
  buildProposalsNow,
  fetchDashboardData,
  rejectProposal,
  runManualAnalysis,
  syncHoldingsNow,
} from "@/lib/api";
import type { DashboardData } from "@/lib/types";

const REFRESH_INTERVAL_MS = 30_000;
const THEME_KEY = "auto-trade-stock-theme";

type Theme = "light" | "dark";
type FeedbackTone = "success" | "error";

function getInitialTheme(): Theme {
  const stored = window.localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function isQuotaError(message: string): boolean {
  return /insufficient_quota|quota is exhausted|exceeded your current quota/i.test(message);
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeProposalId, setActiveProposalId] = useState<number | null>(null);
  const [activeSignalId, setActiveSignalId] = useState<number | null>(null);
  const [activeTaskKey, setActiveTaskKey] = useState<string | null>(null);
  const [taskFeedback, setTaskFeedback] = useState<{ tone: FeedbackTone; message: string } | null>(null);

  const loadDashboard = async () => {
    try {
      const dashboard = await fetchDashboardData();
      setData(dashboard);
      setError(null);
    } catch (fetchError) {
      setError(getErrorMessage(fetchError, "알 수 없는 오류가 발생했습니다."));
    } finally {
      setLoading(false);
    }
  };

  const handleManualTask = async (
    taskKey: string,
    action: () => Promise<{ message: string }>,
    fallbackError: string,
  ) => {
    setActiveTaskKey(taskKey);
    try {
      const result = await action();
      setTaskFeedback({ tone: "success", message: result.message });
      await loadDashboard();
    } catch (taskError) {
      setTaskFeedback({ tone: "error", message: getErrorMessage(taskError, fallbackError) });
    } finally {
      setActiveTaskKey(null);
    }
  };

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      if (!mounted) {
        return;
      }
      await loadDashboard();
    };

    void load();
    const intervalId = window.setInterval(() => {
      void load();
    }, REFRESH_INTERVAL_MS);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const handleApprove = async (proposalId: number) => {
    setActiveProposalId(proposalId);
    try {
      await approveProposal(proposalId);
      setTaskFeedback({ tone: "success", message: `제안 #${proposalId}를 승인하고 키움으로 주문을 전송했습니다.` });
      await loadDashboard();
    } catch (actionError) {
      setTaskFeedback({
        tone: "error",
        message: getErrorMessage(actionError, "주문 제안을 승인하지 못했습니다."),
      });
    } finally {
      setActiveProposalId(null);
    }
  };

  const handleReject = async (proposalId: number) => {
    setActiveProposalId(proposalId);
    try {
      await rejectProposal(proposalId);
      setTaskFeedback({ tone: "success", message: `제안 #${proposalId}를 거절했습니다.` });
      await loadDashboard();
    } catch (actionError) {
      setTaskFeedback({
        tone: "error",
        message: getErrorMessage(actionError, "주문 제안을 거절하지 못했습니다."),
      });
    } finally {
      setActiveProposalId(null);
    }
  };

  const handleExecuteSignal = async (signalId: number) => {
    setActiveSignalId(signalId);
    try {
      const result = await executeSignal(signalId);
      setTaskFeedback({ tone: "success", message: result.message });
      await loadDashboard();
    } catch (actionError) {
      setTaskFeedback({
        tone: "error",
        message: getErrorMessage(actionError, "AI 시그널 주문을 실행하지 못했습니다."),
      });
    } finally {
      setActiveSignalId(null);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 bg-grid bg-[size:44px_44px] opacity-20" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[38rem] bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.22),transparent_52%),radial-gradient(circle_at_20%_20%,rgba(249,115,22,0.18),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.78),transparent_72%)] dark:bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.24),transparent_52%),radial-gradient(circle_at_20%_20%,rgba(249,115,22,0.14),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.74),transparent_72%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-7xl flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8">
        <header className="rounded-[2rem] border border-border/70 bg-card/80 p-6 shadow-panel backdrop-blur">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-background/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5" />
                로컬 AI 트레이딩 대시보드
              </div>
              <div className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
                  AI 시그널, 키움 보유 종목, 실주문 이력을 한 화면에서 확인합니다.
                </h1>
                <p className="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
                  백엔드는 뉴스를 점수화해 SQLite에 저장하고, 주문 제안을 만들거나 시그널 버튼을 통한
                  사용자 직접 주문을 키움으로 전송합니다.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                onClick={async () => {
                  setLoading(true);
                  await loadDashboard();
                }}
              >
                <RefreshCcw className="mr-2 h-4 w-4" />
                새로고침
              </Button>
              <ThemeToggle
                theme={theme}
                onToggle={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
              />
            </div>
          </div>

          <Separator className="my-6" />

          <div className="grid gap-4 text-sm text-muted-foreground md:grid-cols-3">
            <div className="flex items-center gap-3 rounded-2xl bg-background/60 p-4">
              <ListChecks className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-foreground">주문 제안 큐</p>
                <p>제안 테이블에서는 승인 후 주문이 전송됩니다.</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl bg-background/60 p-4">
              <Wallet className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-foreground">키움 보유 종목</p>
                <p>현재 계좌 보유 현황이 SQLite에 동기화됩니다.</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl bg-background/60 p-4">
              <Activity className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-foreground">실시간 스케줄러</p>
                <p>뉴스 분석은 설정된 작업 시간대에만 실행됩니다.</p>
              </div>
            </div>
          </div>
        </header>

        <MetricsStrip data={data} loading={loading} />

        {error ? (
          <section className="rounded-[1.75rem] border border-danger/40 bg-danger/10 p-5 text-sm text-danger">
            대시보드 데이터를 불러오지 못했습니다. {error}
          </section>
        ) : null}

        <section className="rounded-[1.75rem] border border-border/70 bg-card/80 p-5 shadow-panel backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                수동 실행
              </div>
              <div>
                <h2 className="text-xl font-semibold text-foreground">원할 때 즉시 분석 실행</h2>
                <p className="text-sm text-muted-foreground">
                  스케줄러를 기다리지 않고 보유 종목 동기화, 제안 재생성, 전체 AI 분석을 직접 실행할 수 있습니다.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                disabled={activeTaskKey !== null}
                onClick={() =>
                  void handleManualTask(
                    "sync-holdings",
                    syncHoldingsNow,
                    "키움 보유 종목을 동기화하지 못했습니다.",
                  )
                }
              >
                <Wallet className="mr-2 h-4 w-4" />
                {activeTaskKey === "sync-holdings" ? "동기화 중..." : "보유 종목 동기화"}
              </Button>
              <Button
                variant="secondary"
                disabled={activeTaskKey !== null}
                onClick={() =>
                  void handleManualTask(
                    "build-proposals",
                    buildProposalsNow,
                    "주문 제안을 생성하지 못했습니다.",
                  )
                }
              >
                <ListChecks className="mr-2 h-4 w-4" />
                {activeTaskKey === "build-proposals" ? "생성 중..." : "주문 제안 생성"}
              </Button>
              <Button
                disabled={activeTaskKey !== null}
                onClick={() =>
                  void handleManualTask(
                    "run-analysis",
                    runManualAnalysis,
                    "수동 AI 분석을 실행하지 못했습니다.",
                  )
                }
              >
                <Activity className="mr-2 h-4 w-4" />
                {activeTaskKey === "run-analysis" ? "분석 중..." : "지금 AI 분석 실행"}
              </Button>
            </div>
          </div>

          {taskFeedback ? (
            <div
              className={
                taskFeedback.tone === "success"
                  ? "mt-4 rounded-2xl border border-primary/30 bg-primary/5 p-4 text-sm text-foreground"
                  : "mt-4 rounded-2xl border border-danger/40 bg-danger/10 p-4 text-sm text-danger"
              }
            >
              <p>{taskFeedback.message}</p>
              {taskFeedback.tone === "error" && isQuotaError(taskFeedback.message) ? (
                <p className="mt-2 text-xs text-danger/90">
                  OpenAI 쿼터가 부족하면 새 AI 시그널과 제안 생성은 막히지만, 보유 종목 동기화와 기존 주문 승인은 계속 사용할 수 있습니다.
                </p>
              ) : null}
            </div>
          ) : null}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.45fr_0.9fr]">
          <ProposalsTable
            proposals={data?.proposals ?? []}
            loading={loading}
            marketOpen={Boolean(data?.status.market_open)}
            activeProposalId={activeProposalId}
            onApprove={handleApprove}
            onReject={handleReject}
          />
          <HoldingsPanel
            holdings={data?.holdings ?? []}
            accountNo={data?.status.active_account_no ?? null}
            loading={loading}
          />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
          <TradesTable trades={data?.trades ?? []} loading={loading} />
          <SignalPanel
            signals={data?.signals ?? []}
            summary={data?.status.last_ai_summary ?? null}
            marketOpen={Boolean(data?.status.market_open)}
            activeSignalId={activeSignalId}
            onExecuteSignal={handleExecuteSignal}
          />
        </section>

        <LogsPanel logs={data?.logs ?? []} loading={loading} />
      </main>
    </div>
  );
}
