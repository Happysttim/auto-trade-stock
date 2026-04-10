import { ArrowDownRight, ArrowUpRight, Search, Sparkles } from "lucide-react";

import { SectionShell } from "@/components/dashboard/section-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { KeywordAnalysisResult, KeywordRecommendation } from "@/lib/types";

type KeywordAnalysisPanelProps = {
  keyword: string;
  loading: boolean;
  result: KeywordAnalysisResult | null;
  error: string | null;
  onKeywordChange: (value: string) => void;
  onSubmit: () => Promise<void>;
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

function recommendationVariant(signalType: KeywordRecommendation["signal_type"]) {
  if (signalType === "buy") {
    return "success" as const;
  }
  if (signalType === "sell") {
    return "danger" as const;
  }
  return "outline" as const;
}

function recommendationLabel(signalType: KeywordRecommendation["signal_type"]) {
  if (signalType === "buy") {
    return "매수 제안";
  }
  if (signalType === "sell") {
    return "매도 제안";
  }
  return "관망";
}

export function KeywordAnalysisPanel({
  keyword,
  loading,
  result,
  error,
  onKeywordChange,
  onSubmit,
}: KeywordAnalysisPanelProps) {
  return (
    <SectionShell
      eyebrow="Keyword Research"
      title="관심 키워드 즉시 분석"
      description="사용자가 요청한 키워드를 기준으로 최신 뉴스를 읽고, 직접 관련성이 높은 종목만 추려 현재 계좌 기준 제안을 만듭니다."
    >
      <form
        className="flex flex-col gap-3 lg:flex-row"
        onSubmit={async (event) => {
          event.preventDefault();
          await onSubmit();
        }}
      >
        <div className="flex-1">
          <Input
            value={keyword}
            onChange={(event) => onKeywordChange(event.target.value)}
            placeholder="예: 반도체, 전기차, 환율, AI 서버, 해운"
          />
        </div>
        <Button type="submit" disabled={loading || keyword.trim().length < 2}>
          <Search className="mr-2 h-4 w-4" />
          {loading ? "분석 중..." : "키워드 분석"}
        </Button>
      </form>

      {error ? <div className="mt-4 rounded-2xl bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div> : null}

      {result ? (
        <div className="mt-5 space-y-5">
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl bg-muted/55 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">분석 키워드</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{result.keyword}</p>
            </div>
            <div className="rounded-2xl bg-muted/55 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">즉시 매수 가능 금액</p>
              <p className="mt-1 text-lg font-semibold text-foreground">
                {formatCurrency(result.account.available_buying_power)}
              </p>
            </div>
            <div className="rounded-2xl bg-muted/55 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">보유 종목 수</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{result.account.holding_count}개</p>
            </div>
            <div className="rounded-2xl bg-muted/55 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">자동 등록된 제안</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{result.registered_proposals.length}건</p>
            </div>
          </div>

          <div className="rounded-2xl bg-accent/40 px-4 py-4">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Sparkles className="h-4 w-4 text-primary" />
              AI 요약
            </div>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">{result.summary}</p>
            {result.skip_reason ? <p className="mt-2 text-xs text-muted-foreground">{result.skip_reason}</p> : null}
            <p className="mt-2 text-xs text-muted-foreground">분석 시각: {formatDateTime(result.analyzed_at)}</p>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium text-foreground">제안 종목 주문</p>
            {result.recommendations.length === 0 ? (
              <div className="rounded-2xl bg-muted/50 px-4 py-5 text-sm text-muted-foreground">
                현재 키워드로는 실행 가능한 직접 연관 종목 제안이 없습니다.
              </div>
            ) : (
              <div className="grid gap-4 xl:grid-cols-3">
                {result.recommendations.map((recommendation, index) => (
                  <Card key={`${recommendation.symbol}-${index}`} className="h-full">
                    <CardHeader className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <CardTitle>{recommendation.company_name || recommendation.symbol}</CardTitle>
                          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                            {recommendation.symbol}
                          </p>
                        </div>
                        <Badge variant={recommendationVariant(recommendation.signal_type)}>
                          {recommendation.signal_type === "buy" ? (
                            <ArrowUpRight className="mr-1.5 h-3.5 w-3.5" />
                          ) : recommendation.signal_type === "sell" ? (
                            <ArrowDownRight className="mr-1.5 h-3.5 w-3.5" />
                          ) : null}
                          {recommendationLabel(recommendation.signal_type)}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid gap-3 text-sm sm:grid-cols-2">
                        <div>
                          <p className="text-muted-foreground">점수</p>
                          <p className="font-semibold text-foreground">{recommendation.score} / 100</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">보유 예상 기간</p>
                          <p className="font-semibold text-foreground">{recommendation.hold_days}일</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">기준 가격</p>
                          <p className="font-semibold text-foreground">
                            {formatCurrency(recommendation.reference_price)}
                          </p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">권장 수량</p>
                          <p className="font-semibold text-foreground">
                            {recommendation.suggested_quantity != null
                              ? `${recommendation.suggested_quantity.toLocaleString("ko-KR")}주`
                              : "-"}
                          </p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">예상 금액</p>
                          <p className="font-semibold text-foreground">
                            {formatCurrency(recommendation.suggested_amount)}
                          </p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">거래량 비율</p>
                          <p className="font-semibold text-foreground">{recommendation.volume_ratio.toFixed(2)}배</p>
                        </div>
                      </div>

                      <p className="text-sm leading-6 text-muted-foreground">{recommendation.rationale}</p>

                      <div className="rounded-2xl bg-muted/60 px-4 py-3 text-xs text-muted-foreground">
                        {recommendation.signal_type === "buy" ? (
                          <p>
                            현재 최대 매수 가능 수량은 {recommendation.max_affordable_quantity.toLocaleString("ko-KR")}주이며,
                            안정 거래량 판정은 {recommendation.stable_volume ? "통과" : "미통과"}입니다.
                          </p>
                        ) : (
                          <p>현재 보유 수량은 {recommendation.currently_held_quantity.toLocaleString("ko-KR")}주입니다.</p>
                        )}
                        {recommendation.registered_proposal_id ? (
                          <p className="mt-2 text-foreground">주문 제안 리스트에 자동 등록되었습니다. #{recommendation.registered_proposal_id}</p>
                        ) : null}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </SectionShell>
  );
}
