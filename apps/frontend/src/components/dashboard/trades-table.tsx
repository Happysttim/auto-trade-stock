import { ArrowDownRight, ArrowUpRight, CandlestickChart } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { TradeRecord } from "@/lib/types";

type TradesTableProps = {
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

export function TradesTable({ trades, loading }: TradesTableProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-primary/12 p-3 text-primary">
            <CandlestickChart className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>주문 이력</CardTitle>
            <CardDescription>사용자 확인 후 키움으로 전송된 주문 기록</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
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
                  최신 주문 이력을 불러오는 중입니다...
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
                    <p className="font-semibold">{trade.company_name || trade.symbol}</p>
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{trade.symbol}</p>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={trade.trade_type === "buy" ? "success" : "danger"}>
                    <span className="mr-1.5 inline-flex">
                      {trade.trade_type === "buy" ? (
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      ) : (
                        <ArrowDownRight className="h-3.5 w-3.5" />
                      )}
                    </span>
                    {trade.trade_type === "buy" ? "매수" : "매도"}
                  </Badge>
                </TableCell>
                <TableCell>{trade.quantity.toLocaleString("ko-KR")}</TableCell>
                <TableCell>{formatCurrency(trade.price)}</TableCell>
                <TableCell>{formatCurrency(trade.total_amount)}</TableCell>
                <TableCell
                  className={
                    trade.pnl == null ? "text-muted-foreground" : trade.pnl < 0 ? "text-danger" : "text-success"
                  }
                >
                  {formatCurrency(trade.pnl)}
                </TableCell>
                <TableCell>{{ submitted: "전송 완료" }[trade.status] ?? trade.status}</TableCell>
                <TableCell className="text-muted-foreground">{formatDateTime(trade.executed_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
