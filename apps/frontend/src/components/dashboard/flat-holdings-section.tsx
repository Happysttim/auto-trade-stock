import { SectionShell } from "@/components/dashboard/section-shell";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { HoldingRecord } from "@/lib/types";

type FlatHoldingsSectionProps = {
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

export function FlatHoldingsSection({ holdings, accountNo, loading }: FlatHoldingsSectionProps) {
  return (
    <SectionShell
      eyebrow="Holdings"
      title="현재 보유 종목"
      description={accountNo ? `계좌 ${accountNo} 기준 최신 보유 현황입니다.` : "동기화된 계좌 기준 보유 현황입니다."}
    >
      <Table className="min-w-[820px]">
        <TableHeader>
          <TableRow>
            <TableHead>종목</TableHead>
            <TableHead className="whitespace-nowrap">보유 수량</TableHead>
            <TableHead className="whitespace-nowrap">주문 가능</TableHead>
            <TableHead className="whitespace-nowrap">평균 단가</TableHead>
            <TableHead className="whitespace-nowrap">현재가</TableHead>
            <TableHead className="whitespace-nowrap">평가 금액</TableHead>
            <TableHead className="whitespace-nowrap">손익</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                보유 종목을 불러오는 중입니다...
              </TableCell>
            </TableRow>
          ) : null}

          {!loading && holdings.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                동기화된 보유 종목이 없습니다.
              </TableCell>
            </TableRow>
          ) : null}

          {holdings.map((holding) => (
            <TableRow key={`${holding.account_no ?? "default"}-${holding.symbol}`}>
              <TableCell className="min-w-[180px]">
                <div className="space-y-1">
                  <p className="truncate font-semibold text-foreground">{holding.company_name || holding.symbol}</p>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{holding.symbol}</p>
                </div>
              </TableCell>
              <TableCell className="whitespace-nowrap">{holding.quantity.toLocaleString("ko-KR")}주</TableCell>
              <TableCell className="whitespace-nowrap">{holding.available_quantity.toLocaleString("ko-KR")}주</TableCell>
              <TableCell className="whitespace-nowrap">{formatCurrency(holding.average_price)}</TableCell>
              <TableCell className="whitespace-nowrap">{formatCurrency(holding.current_price)}</TableCell>
              <TableCell className="whitespace-nowrap">{formatCurrency(holding.market_value)}</TableCell>
              <TableCell
                className={`whitespace-nowrap ${holding.pnl != null && holding.pnl < 0 ? "text-danger" : "text-success"}`}
              >
                {formatCurrency(holding.pnl)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </SectionShell>
  );
}
