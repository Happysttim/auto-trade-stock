import { Wallet } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { HoldingRecord } from "@/lib/types";

type HoldingsPanelProps = {
  holdings: HoldingRecord[];
  accountNo: string | null;
  loading: boolean;
};

function formatCurrency(value: number | null) {
  if (value == null) {
    return "-";
  }
  return new Intl.NumberFormat("ko-KR", {
    style: "currency",
    currency: "KRW",
    maximumFractionDigits: 0,
  }).format(value);
}

export function HoldingsPanel({ holdings, accountNo, loading }: HoldingsPanelProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-primary/12 p-3 text-primary">
            <Wallet className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>Kiwoom Holdings</CardTitle>
            <CardDescription>
              {accountNo ? `Live snapshot for account ${accountNo}` : "Latest broker holdings snapshot"}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? <p className="text-sm text-muted-foreground">Loading holdings snapshot...</p> : null}

        {!loading && holdings.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/80 p-5 text-sm text-muted-foreground">
            No holdings have been synced from Kiwoom yet.
          </div>
        ) : null}

        {holdings.map((holding, index) => (
          <div key={`${holding.account_no ?? "default"}-${holding.symbol}`} className="space-y-3 rounded-2xl bg-background/60 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{holding.company_name || holding.symbol}</p>
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{holding.symbol}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold">{holding.quantity.toLocaleString("ko-KR")} shares</p>
                <p className="text-xs text-muted-foreground">
                  Available {holding.available_quantity.toLocaleString("ko-KR")}
                </p>
              </div>
            </div>

            <div className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <p className="text-muted-foreground">Average Price</p>
                <p className="font-semibold">{formatCurrency(holding.average_price)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Current Price</p>
                <p className="font-semibold">{formatCurrency(holding.current_price)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Market Value</p>
                <p className="font-semibold">{formatCurrency(holding.market_value)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">PnL</p>
                <p className={holding.pnl != null && holding.pnl < 0 ? "font-semibold text-danger" : "font-semibold text-success"}>
                  {formatCurrency(holding.pnl)}
                </p>
              </div>
            </div>

            {index < holdings.length - 1 ? <Separator /> : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
