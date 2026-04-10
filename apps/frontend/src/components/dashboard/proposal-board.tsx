import { ArrowDownRight, ArrowUpRight, Check, ListChecks, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { OrderProposal } from "@/lib/types";

type ProposalBoardProps = {
  proposals: OrderProposal[];
  loading: boolean;
  marketOpen: boolean;
  activeProposalId: number | null;
  onApprove: (proposalId: number) => Promise<void>;
  onReject: (proposalId: number) => Promise<void>;
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

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusVariant(status: string): "default" | "success" | "danger" | "outline" {
  if (status === "pending_approval") {
    return "default";
  }
  if (status === "executed") {
    return "success";
  }
  if (status === "failed" || status === "rejected") {
    return "danger";
  }
  return "outline";
}

function statusLabel(status: string) {
  return (
    {
      pending_approval: "승인 대기",
      executed: "주문 완료",
      failed: "실패",
      rejected: "거절",
    }[status] ?? status
  );
}

export function ProposalBoard({
  proposals,
  loading,
  marketOpen,
  activeProposalId,
  onApprove,
  onReject,
}: ProposalBoardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-primary/12 p-3 text-primary">
            <ListChecks className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>주문 제안</CardTitle>
            <CardDescription>사용자가 바로 승인하거나 거절할 수 있는 주문 목록입니다.</CardDescription>
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
              <TableHead>기준가</TableHead>
              <TableHead>예상 금액</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>생성 시각</TableHead>
              <TableHead className="text-right">작업</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                  주문 제안을 불러오는 중입니다...
                </TableCell>
              </TableRow>
            ) : null}

            {!loading && proposals.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                  현재 승인 대기 중인 주문 제안이 없습니다.
                </TableCell>
              </TableRow>
            ) : null}

            {proposals.map((proposal) => {
              const isPending = proposal.status === "pending_approval";
              const isBusy = activeProposalId === proposal.id;
              return (
                <TableRow key={proposal.id}>
                  <TableCell>
                    <div className="space-y-1">
                      <p className="font-semibold text-foreground">{proposal.company_name || proposal.symbol}</p>
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{proposal.symbol}</p>
                      {proposal.reason ? <p className="text-xs text-muted-foreground">{proposal.reason}</p> : null}
                      {proposal.last_error ? <p className="text-xs text-danger">{proposal.last_error}</p> : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={proposal.proposal_type === "buy" ? "success" : "danger"}>
                      {proposal.proposal_type === "buy" ? (
                        <ArrowUpRight className="mr-1.5 h-3.5 w-3.5" />
                      ) : (
                        <ArrowDownRight className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      {proposal.proposal_type === "buy" ? "매수" : "매도"}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{proposal.quantity.toLocaleString("ko-KR")}주</TableCell>
                  <TableCell className="whitespace-nowrap">{formatCurrency(proposal.reference_price)}</TableCell>
                  <TableCell className="whitespace-nowrap">{formatCurrency(proposal.target_amount)}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(proposal.status)}>{statusLabel(proposal.status)}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(proposal.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <Button
                        size="icon"
                        disabled={!isPending || !marketOpen || isBusy}
                        onClick={async () => onApprove(proposal.id)}
                        aria-label={`제안 ${proposal.id} 승인`}
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="secondary"
                        size="icon"
                        disabled={!isPending || isBusy}
                        onClick={async () => onReject(proposal.id)}
                        aria-label={`제안 ${proposal.id} 거절`}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
