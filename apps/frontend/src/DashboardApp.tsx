import { useEffect, useState } from "react";
import { Activity, RefreshCcw, ShieldCheck, Wallet } from "lucide-react";

import { FlatHoldingsSection } from "@/components/dashboard/flat-holdings-section";
import { FlatLogsSection } from "@/components/dashboard/flat-logs-section";
import { FlatSignalsSection } from "@/components/dashboard/flat-signals-section";
import { FlatTradesSection } from "@/components/dashboard/flat-trades-section";
import { KeywordAnalysisPanel } from "@/components/dashboard/keyword-analysis-panel";
import { ProposalBoard } from "@/components/dashboard/proposal-board";
import { SectionShell } from "@/components/dashboard/section-shell";
import { StatusStrip } from "@/components/dashboard/status-strip";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  approveProposal,
  buildProposalsNow,
  executeSignal,
  fetchDashboardData,
  rejectProposal,
  runKeywordAnalysis,
  runManualAnalysis,
  syncHoldingsNow,
} from "@/lib/api";
import type { DashboardData, KeywordAnalysisResult } from "@/lib/types";

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

export default function DashboardApp() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [data, setData] = useState<DashboardData | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [activeProposalId, setActiveProposalId] = useState<number | null>(null);
  const [activeSignalId, setActiveSignalId] = useState<number | null>(null);
  const [activeTaskKey, setActiveTaskKey] = useState<string | null>(null);
  const [taskFeedback, setTaskFeedback] = useState<{ tone: FeedbackTone; message: string } | null>(null);
  const [keyword, setKeyword] = useState("");
  const [keywordLoading, setKeywordLoading] = useState(false);
  const [keywordError, setKeywordError] = useState<string | null>(null);
  const [keywordResult, setKeywordResult] = useState<KeywordAnalysisResult | null>(null);

  const loadDashboard = async (withLoader = false) => {
    if (withLoader) {
      setDashboardLoading(true);
    }
    try {
      const dashboard = await fetchDashboardData();
      setData(dashboard);
      setDashboardError(null);
    } catch (fetchError) {
      setDashboardError(getErrorMessage(fetchError, "대시보드 데이터를 불러오지 못했습니다."));
    } finally {
      setDashboardLoading(false);
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
      await loadDashboard(!data);
    };

    void load();
    const intervalId = window.setInterval(() => {
      void loadDashboard();
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
      setTaskFeedback({ tone: "success", message: `제안 #${proposalId}를 승인하고 키움 주문을 전송했습니다.` });
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

  const handleKeywordAnalysis = async () => {
    const normalizedKeyword = keyword.trim();
    if (normalizedKeyword.length < 2) {
      setKeywordError("키워드는 2글자 이상 입력해주세요.");
      return;
    }

    setKeywordLoading(true);
    setKeywordError(null);
    try {
      const result = await runKeywordAnalysis(normalizedKeyword);
      setKeywordResult(result);
      await loadDashboard();
    } catch (analysisError) {
      setKeywordError(getErrorMessage(analysisError, "키워드 분석을 실행하지 못했습니다."));
    } finally {
      setKeywordLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 bg-grid bg-[size:44px_44px] opacity-10" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[28rem] bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.22),transparent_52%),radial-gradient(circle_at_15%_15%,rgba(249,115,22,0.16),transparent_24%),linear-gradient(180deg,rgba(255,255,255,0.68),transparent_72%)] dark:bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.24),transparent_52%),radial-gradient(circle_at_15%_15%,rgba(249,115,22,0.14),transparent_24%),linear-gradient(180deg,rgba(15,23,42,0.74),transparent_72%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="rounded-[1.75rem] bg-background/50 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full bg-background/80 px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5" />
                Local AI Trading Desk
              </div>
              <div className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
                  키워드 분석, 주문 제안, 보유 종목, 주문 이력을 한 화면에서 봅니다.
                </h1>
                <p className="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
                  정규 AI 분석은 기존 스케줄대로 동작하고, 사용자가 입력한 키워드는 시간과 무관하게 즉시 분석합니다.
                  현재 계좌 예수금과 보유 종목을 기준으로 매수 또는 매도 아이디어를 계산합니다.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                onClick={async () => {
                  await loadDashboard(true);
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
        </header>

        <StatusStrip data={data} loading={dashboardLoading} />

        {dashboardError ? (
          <section className="rounded-[1.5rem] bg-danger/10 px-5 py-4 text-sm text-danger">
            {dashboardError}
          </section>
        ) : null}

        <KeywordAnalysisPanel
          keyword={keyword}
          loading={keywordLoading}
          result={keywordResult}
          error={keywordError}
          onKeywordChange={setKeyword}
          onSubmit={handleKeywordAnalysis}
        />

        <SectionShell
          eyebrow="Manual Control"
          title="수동 실행"
          description="정규 스케줄을 기다리지 않고 보유 종목 동기화, 제안 생성, 전체 AI 분석을 바로 실행할 수 있습니다."
          actions={
            <>
              <Button
                variant="secondary"
                disabled={activeTaskKey !== null}
                onClick={() =>
                  void handleManualTask(
                    "sync-holdings",
                    syncHoldingsNow,
                    "보유 종목을 동기화하지 못했습니다.",
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
                {activeTaskKey === "build-proposals" ? "생성 중..." : "주문 제안 생성"}
              </Button>
              <Button
                disabled={activeTaskKey !== null}
                onClick={() =>
                  void handleManualTask(
                    "run-analysis",
                    runManualAnalysis,
                    "전체 AI 분석을 실행하지 못했습니다.",
                  )
                }
              >
                <Activity className="mr-2 h-4 w-4" />
                {activeTaskKey === "run-analysis" ? "분석 중..." : "지금 AI 분석 실행"}
              </Button>
            </>
          }
        >
          {taskFeedback ? (
            <div
              className={
                taskFeedback.tone === "success"
                  ? "rounded-2xl bg-primary/5 px-4 py-3 text-sm text-foreground"
                  : "rounded-2xl bg-danger/10 px-4 py-3 text-sm text-danger"
              }
            >
              <p>{taskFeedback.message}</p>
              {taskFeedback.tone === "error" && isQuotaError(taskFeedback.message) ? (
                <p className="mt-2 text-xs text-danger/90">
                  OpenAI 쿼터가 부족하면 AI 분석과 제안 생성은 멈추지만, 보유 종목 동기화와 기존 주문 승인 기능은 계속 사용할 수 있습니다.
                </p>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">필요한 작업만 골라서 즉시 실행할 수 있습니다.</p>
          )}
        </SectionShell>

        <ProposalBoard
          proposals={data?.proposals ?? []}
          loading={dashboardLoading}
          marketOpen={Boolean(data?.status.market_open)}
          activeProposalId={activeProposalId}
          onApprove={handleApprove}
          onReject={handleReject}
        />

        <FlatHoldingsSection
          holdings={data?.holdings ?? []}
          accountNo={data?.status.active_account_no ?? null}
          loading={dashboardLoading}
        />

        <FlatSignalsSection
          signals={data?.signals ?? []}
          summary={data?.status.last_ai_summary ?? null}
          marketOpen={Boolean(data?.status.market_open)}
          activeSignalId={activeSignalId}
          onExecuteSignal={handleExecuteSignal}
        />

        <FlatTradesSection trades={data?.trades ?? []} loading={dashboardLoading} />

        <FlatLogsSection logs={data?.logs ?? []} loading={dashboardLoading} />
      </main>
    </div>
  );
}
