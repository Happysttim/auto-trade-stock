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
            <CardTitle>키움 보유 종목</CardTitle>
            <CardDescription>
              {accountNo ? `계좌 ${accountNo}의 최신 보유 현황` : "가장 최근에 동기화된 보유 현황"}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? <p className="text-sm text-muted-foreground">보유 종목을 불러오는 중입니다...</p> : null}

        {!loading && holdings.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/80 p-5 text-sm text-muted-foreground">
            아직 키움에서 동기화된 보유 종목이 없습니다.
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
                <p className="text-sm font-semibold">{holding.quantity.toLocaleString("ko-KR")}주</p>
                <p className="text-xs text-muted-foreground">
                  주문 가능 {holding.available_quantity.toLocaleString("ko-KR")}주
                </p>
              </div>
            </div>

            <div className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <p className="text-muted-foreground">평균 단가</p>
                <p className="font-semibold">{formatCurrency(holding.average_price)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">현재가</p>
                <p className="font-semibold">{formatCurrency(holding.current_price)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">평가 금액</p>
                <p className="font-semibold">{formatCurrency(holding.market_value)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">손익</p>
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
