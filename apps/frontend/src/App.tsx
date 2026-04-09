import { useEffect, useState } from "react";
import { Activity, ListChecks, RefreshCcw, ShieldCheck, Wallet } from "lucide-react";

import { HoldingsPanel } from "@/components/dashboard/holdings-panel";
import { LogsPanel } from "@/components/dashboard/logs-panel";
import { MetricsStrip } from "@/components/dashboard/metrics-strip";
import { ProposalsTable } from "@/components/dashboard/proposals-table";
import { SignalPanel } from "@/components/dashboard/signal-panel";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { TradesTable } from "@/components/dashboard/trades-table";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { approveProposal, fetchDashboardData, rejectProposal } from "@/lib/api";
import type { DashboardData } from "@/lib/types";

const REFRESH_INTERVAL_MS = 30_000;
const THEME_KEY = "auto-trade-stock-theme";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const stored = window.localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeProposalId, setActiveProposalId] = useState<number | null>(null);

  const loadDashboard = async () => {
    try {
      const dashboard = await fetchDashboardData();
      setData(dashboard);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unknown error");
    } finally {
      setLoading(false);
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
      await loadDashboard();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to approve proposal.");
    } finally {
      setActiveProposalId(null);
    }
  };

  const handleReject = async (proposalId: number) => {
    setActiveProposalId(proposalId);
    try {
      await rejectProposal(proposalId);
      await loadDashboard();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Failed to reject proposal.");
    } finally {
      setActiveProposalId(null);
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
                Local AI Approval Trading Console
              </div>
              <div className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
                  AI proposals, Kiwoom holdings, and user-approved orders in one live dashboard.
                </h1>
                <p className="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
                  The backend scores current news, stores signals in SQLite, builds order proposals,
                  and sends orders to Kiwoom only after you approve them here.
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
                Refresh
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
                <p className="font-medium text-foreground">Proposal Queue</p>
                <p>User approval is required before any Kiwoom order is sent</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl bg-background/60 p-4">
              <Wallet className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-foreground">Kiwoom Holdings</p>
                <p>Current account holdings are synced into SQLite for review</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl bg-background/60 p-4">
              <Activity className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-foreground">Live Scheduler</p>
                <p>News analysis only runs during the configured working window</p>
              </div>
            </div>
          </div>
        </header>

        <MetricsStrip data={data} loading={loading} />

        {error ? (
          <section className="rounded-[1.75rem] border border-danger/40 bg-danger/10 p-5 text-sm text-danger">
            Failed to load dashboard data. {error}
          </section>
        ) : null}

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
          <SignalPanel signals={data?.signals ?? []} summary={data?.status.last_ai_summary ?? null} />
        </section>

        <LogsPanel logs={data?.logs ?? []} loading={loading} />
      </main>
    </div>
  );
}
