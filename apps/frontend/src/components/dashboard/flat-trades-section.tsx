import { Badge } from "@/components/ui/badge";
import { SectionShell } from "@/components/dashboard/section-shell";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { TradeRecord } from "@/lib/types";

type FlatTradesSectionProps = {
  trades: TradeRecord[];
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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function FlatTradesSection({ trades, loading }: FlatTradesSectionProps) {
  return (
    <SectionShell eyebrow="Trades" title="주문 이력" description="실제로 전송된 매수 및 매도 주문 기록입니다.">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>종목</TableHead>
            <TableHead>유형</TableHead>
            <TableHead>수량</TableHead>
            <TableHead>가격</TableHead>
            <TableHead>총액</TableHead>
            <TableHead>손익</TableHead>
            <TableHead>상태</TableHead>
            <TableHead>시각</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                주문 이력을 불러오는 중입니다...
              </TableCell>
            </TableRow>
          ) : null}

          {!loading && trades.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                아직 기록된 주문 이력이 없습니다.
              </TableCell>
            </TableRow>
          ) : null}

          {trades.map((trade) => (
            <TableRow key={trade.id}>
              <TableCell>
                <div className="space-y-1">
                  <p className="font-semibold text-foreground">{trade.company_name || trade.symbol}</p>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{trade.symbol}</p>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={trade.trade_type === "buy" ? "success" : "danger"}>
                  {trade.trade_type === "buy" ? "매수" : "매도"}
                </Badge>
              </TableCell>
              <TableCell className="whitespace-nowrap">{trade.quantity.toLocaleString("ko-KR")}주</TableCell>
              <TableCell className="whitespace-nowrap">{formatCurrency(trade.price)}</TableCell>
              <TableCell className="whitespace-nowrap">{formatCurrency(trade.total_amount)}</TableCell>
              <TableCell className={trade.pnl != null && trade.pnl < 0 ? "text-danger whitespace-nowrap" : "text-success whitespace-nowrap"}>
                {formatCurrency(trade.pnl)}
              </TableCell>
              <TableCell>{trade.status === "submitted" ? "전송 완료" : trade.status}</TableCell>
              <TableCell className="text-muted-foreground">{formatDateTime(trade.executed_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </SectionShell>
  );
}
