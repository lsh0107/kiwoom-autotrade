"use client";

import { useState } from "react";
import { useDecisions } from "@/hooks/queries/use-decisions";
import { useReviewDecision } from "@/hooks/mutations/use-review-decision";
import type { LLMDecision } from "@/types/api";
import { formatKRW, formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { BrainCircuit, Clock, CheckCircle2, XCircle } from "lucide-react";

/* ── 상태 필터 ── */
const STATUS_OPTIONS = [
  { value: "all", label: "전체" },
  { value: "pending", label: "대기" },
  { value: "approved", label: "승인" },
  { value: "rejected", label: "거부" },
  { value: "applied", label: "적용" },
  { value: "evaluated", label: "평가" },
] as const;

/* ── 상태 배지 ── */
function StatusBadge({ decision }: { decision: LLMDecision }) {
  const { status } = decision;
  switch (status) {
    case "pending":
      return (
        <Badge className="border-gray-200 bg-gray-50 text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
          <Clock className="mr-1 size-3" />
          검토 필요
        </Badge>
      );
    case "approved":
      // status 가 진실 source — applied_at 유무와 무관하게 "후보" 로 표시.
      // 실제 적용은 loader 가 status="applied" 로 마킹한 뒤에만 "적용 완료".
      return (
        <Badge className="border-yellow-200 bg-yellow-50 text-yellow-700 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-300">
          <Clock className="mr-1 size-3" />
          승인됨 — 다음 실행 시 후보
        </Badge>
      );
    case "applied":
      return (
        <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
          <CheckCircle2 className="mr-1 size-3" />
          적용 완료
        </Badge>
      );
    case "rejected":
      return (
        <Badge className="border-gray-200 bg-blue-50 text-gray-600 dark:border-gray-700 dark:bg-blue-950 dark:text-gray-400">
          <XCircle className="mr-1 size-3" />
          거부됨
        </Badge>
      );
    case "evaluated":
      return (
        <Badge className="border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-300">
          평가
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

/* ── 결정 유형 레이블 ── */
const DECISION_TYPE_LABELS: Record<string, string> = {
  symbol_bias: "종목 편향",
  universe_adjust: "유니버스 조정",
  strategy_param_hint: "전략 파라미터 힌트",
  weight_adjust: "비중 조정",
  risk_mode: "리스크 모드",
  param_tune: "파라미터 튜닝",
  stock_swap: "종목 교체",
};

/* ── 컨텍스트 소스 레이블 ── */
const SOURCE_LABELS: Record<string, string> = {
  overnight: "야간 분석",
  premarket: "장전 분석",
  postmarket: "장후 분석",
  ai_hedge: "AI Hedge",
};

/* ── bias 레이블 ── */
const BIAS_LABELS: Record<string, string> = {
  block_buy: "매수 차단",
  block_sell: "매도 차단",
  boost_buy: "매수 가산",
  boost_sell: "매도 가산",
};

/* ── 리스크 플래그 레이블 ── */
const RISK_FLAG_LABELS: Record<string, string> = {
  POSITION_LIMIT_REACHED: "비중 한도 초과",
  STALE_DATA: "데이터 노후",
  LOW_LIQUIDITY: "유동성 부족",
};

/* ── 요약 행 표시 헬퍼 ── */
function SummaryRow({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex gap-2">
      <span className="min-w-[88px] text-muted-foreground">{label}</span>
      <span className={mono ? "font-mono break-all" : "break-words"}>
        {children}
      </span>
    </div>
  );
}

/* ── 안전 캐스팅 헬퍼 ── */
function asString(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}
function asNumber(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}
function asStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const arr = v.filter((x): x is string => typeof x === "string");
  return arr.length > 0 ? arr : undefined;
}
function asDict(v: unknown): Record<string, unknown> | undefined {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : undefined;
}

function formatPctSigned(value: number): string {
  const pct = value * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

/* ── symbol_bias 요약 ── */
function SymbolBiasSummary({ content }: { content: Record<string, unknown> }) {
  const symbol = asString(content.symbol);
  const bias = asString(content.bias);
  const reason = asString(content.reason);
  const source = asString(content.source);
  const originalAction = asString(content.original_action);
  const riskFlags = asStringArray(content.risk_flags);
  const suggestedQty = asNumber(content.suggested_quantity);
  const suggestedNotional = asNumber(content.suggested_notional_krw);
  const evidence = asDict(content.evidence) ?? {};
  const holdingQty = asNumber(evidence.holding_qty);
  const positionValue = asNumber(evidence.current_position_value);
  const positionLimit = asNumber(evidence.position_limit_krw);
  const latestClose = asNumber(evidence.latest_close);
  const mom20 = asNumber(evidence.momentum_20d);
  const mom60 = asNumber(evidence.momentum_60d);
  const dd60 = asNumber(evidence.drawdown_60d);
  const volRatio = asNumber(evidence.volume_ratio_20d);

  return (
    <div className="space-y-1 text-xs">
      {symbol && (
        <SummaryRow label="종목" mono>
          {symbol}
        </SummaryRow>
      )}
      {bias && (
        <SummaryRow label="판단">{BIAS_LABELS[bias] ?? bias}</SummaryRow>
      )}
      {reason && <SummaryRow label="사유">{reason}</SummaryRow>}
      {(source || originalAction) && (
        <SummaryRow label="출처">
          {source ?? "?"}
          {originalAction ? ` · 원시 액션 ${originalAction}` : ""}
        </SummaryRow>
      )}
      {riskFlags && (
        <SummaryRow label="리스크">
          <span className="flex flex-wrap gap-1">
            {riskFlags.map((f) => (
              <Badge
                key={f}
                variant="outline"
                className="border-amber-300 bg-amber-50 text-[10px] text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300"
              >
                {RISK_FLAG_LABELS[f] ?? f}
              </Badge>
            ))}
          </span>
        </SummaryRow>
      )}
      {(suggestedQty !== undefined || suggestedNotional !== undefined) && (
        <SummaryRow label="제안 수량/금액" mono>
          {suggestedQty !== undefined ? formatNumber(suggestedQty) : "?"}주 ·{" "}
          ₩{suggestedNotional !== undefined ? formatKRW(suggestedNotional) : "?"}
        </SummaryRow>
      )}
      {(holdingQty !== undefined || positionValue !== undefined) && (
        <SummaryRow label="현재 보유" mono>
          {holdingQty !== undefined ? formatNumber(holdingQty) : "?"}주 ·{" "}
          ₩{positionValue !== undefined ? formatKRW(positionValue) : "?"}
        </SummaryRow>
      )}
      {positionLimit !== undefined && (
        <SummaryRow label="비중 한도" mono>
          ₩{formatKRW(positionLimit)}
        </SummaryRow>
      )}
      {(latestClose !== undefined ||
        mom20 !== undefined ||
        mom60 !== undefined ||
        dd60 !== undefined ||
        volRatio !== undefined) && (
        <SummaryRow label="지표" mono>
          <span className="flex flex-wrap gap-x-3 gap-y-0.5">
            {latestClose !== undefined && (
              <span>종가 ₩{formatKRW(latestClose)}</span>
            )}
            {mom20 !== undefined && <span>mom20 {formatPctSigned(mom20)}</span>}
            {mom60 !== undefined && <span>mom60 {formatPctSigned(mom60)}</span>}
            {dd60 !== undefined && <span>dd60 {formatPctSigned(dd60)}</span>}
            {volRatio !== undefined && (
              <span>vol×{volRatio.toFixed(2)}</span>
            )}
          </span>
        </SummaryRow>
      )}
    </div>
  );
}

/* ── universe_adjust 요약 ── */
function UniverseAdjustSummary({
  content,
}: {
  content: Record<string, unknown>;
}) {
  const exclude = asStringArray(content.exclude);
  const add = asStringArray(content.add);
  const reason = asString(content.reason);
  const scope = asString(content.scope) ?? asString(content.affected_scope);

  return (
    <div className="space-y-1 text-xs">
      {exclude && (
        <SummaryRow label="제외 종목" mono>
          {exclude.join(", ")}
        </SummaryRow>
      )}
      {add && (
        <SummaryRow label="추가 종목" mono>
          {add.join(", ")}
        </SummaryRow>
      )}
      {!exclude && !add && (
        <SummaryRow label="변경">변경 종목 없음</SummaryRow>
      )}
      {reason && <SummaryRow label="사유">{reason}</SummaryRow>}
      {scope && <SummaryRow label="영향 범위">{scope}</SummaryRow>}
    </div>
  );
}

/* ── strategy_param_hint 요약 ── */
function StrategyParamHintSummary({
  content,
}: {
  content: Record<string, unknown>;
}) {
  const strategy = asString(content.strategy);
  const reason = asString(content.reason);
  // params 가 별도 키로 있을 수도, content 자체가 params 형식일 수도 있음
  const paramsObj = asDict(content.params);
  const fallbackParams: Record<string, unknown> = paramsObj
    ? paramsObj
    : Object.fromEntries(
        Object.entries(content).filter(
          ([k]) => !["strategy", "reason", "confidence"].includes(k)
        )
      );
  const paramEntries = Object.entries(fallbackParams).filter(
    ([, v]) => typeof v === "number" || typeof v === "string"
  );

  return (
    <div className="space-y-1 text-xs">
      {strategy && <SummaryRow label="전략">{strategy}</SummaryRow>}
      {paramEntries.length > 0 && (
        <SummaryRow label="파라미터" mono>
          <span className="flex flex-col gap-0.5">
            {paramEntries.map(([k, v]) => (
              <span key={k}>
                <span className="text-muted-foreground">{k}</span> ={" "}
                {String(v)}
              </span>
            ))}
          </span>
        </SummaryRow>
      )}
      {reason && <SummaryRow label="사유">{reason}</SummaryRow>}
    </div>
  );
}

/* ── 알 수 없는 타입 fallback ── */
function GenericContentSummary({
  content,
}: {
  content: Record<string, unknown>;
}) {
  const entries = Object.entries(content);
  if (entries.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">표시할 요약이 없습니다.</p>
    );
  }
  return (
    <div className="space-y-1 text-xs">
      {entries.slice(0, 5).map(([k, v]) => (
        <SummaryRow key={k} label={k} mono>
          {typeof v === "object" ? JSON.stringify(v) : String(v)}
        </SummaryRow>
      ))}
    </div>
  );
}

/* ── 타입 디스패처 ── */
function DecisionContentView({ decision }: { decision: LLMDecision }) {
  const content = decision.content ?? {};
  switch (decision.decision_type) {
    case "symbol_bias":
      return <SymbolBiasSummary content={content} />;
    case "universe_adjust":
      return <UniverseAdjustSummary content={content} />;
    case "strategy_param_hint":
      return <StrategyParamHintSummary content={content} />;
    default:
      return <GenericContentSummary content={content} />;
  }
}

/* ── 원본 JSON 토글 ── */
function RawJsonToggle({ content }: { content: unknown }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-[11px] text-muted-foreground hover:text-foreground"
        aria-expanded={open}
        aria-controls="decision-raw-json"
      >
        {open ? "원본 숨기기 ▲" : "원본 보기 ▼"}
      </button>
      {open && (
        <pre
          id="decision-raw-json"
          data-testid="decision-raw-json"
          className="mt-2 max-h-64 overflow-auto rounded-md bg-muted/30 p-2 text-[10px] font-mono whitespace-pre-wrap break-all"
        >
          {JSON.stringify(content, null, 2)}
        </pre>
      )}
    </div>
  );
}

/* ── Skeleton ── */
function DecisionsSkeleton() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-1 h-4 w-64" />
      </div>
      <Skeleton className="h-px w-full" />
      {Array.from({ length: 3 }).map((_, i) => (
        <Skeleton key={i} className="h-40 w-full rounded-lg" />
      ))}
    </div>
  );
}

/* ── 결정 카드 ── */
function DecisionCard({
  decision,
  onApprove,
  onReject,
  isPending,
}: {
  decision: LLMDecision;
  onApprove: () => void;
  onReject: () => void;
  isPending: boolean;
}) {
  const content = decision.content;

  return (
    <div className="rounded-lg border p-4 space-y-3">
      {/* 헤더 */}
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold">
              {DECISION_TYPE_LABELS[decision.decision_type] ??
                decision.decision_type}
            </p>
            <Badge variant="secondary" className="text-[10px]">
              {SOURCE_LABELS[decision.context_source] ??
                decision.context_source}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {new Date(decision.created_at).toLocaleString("ko-KR")}
          </p>
          {decision.status === "applied" && decision.applied_at && (
            <p className="text-xs text-emerald-600 dark:text-emerald-400">
              적용: {new Date(decision.applied_at).toLocaleString("ko-KR")}
            </p>
          )}
        </div>
        <StatusBadge decision={decision} />
      </div>

      {/* 신뢰도 */}
      {decision.confidence != null && (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">신뢰도:</span>
          <span className="font-mono font-medium">
            {(decision.confidence * 100).toFixed(0)}%
          </span>
        </div>
      )}

      {/* 내용 요약 — decision_type 별 핵심 필드만 노출 */}
      <div className="rounded-md bg-muted/50 p-3 space-y-2">
        <DecisionContentView decision={decision} />
        <RawJsonToggle content={content} />
      </div>

      {/* 액션 버튼 (pending만) */}
      {decision.status === "pending" && (
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            className="h-7 bg-emerald-600 text-white hover:bg-emerald-700 dark:bg-emerald-700 dark:hover:bg-emerald-800"
            onClick={onApprove}
            disabled={isPending}
          >
            승인
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-destructive hover:bg-destructive/10"
            onClick={onReject}
            disabled={isPending}
          >
            거부
          </Button>
        </div>
      )}
    </div>
  );
}

/* ── 메인 페이지 ── */
export default function DecisionsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const queryStatus = statusFilter === "all" ? undefined : statusFilter;
  const { data: decisions = [], isLoading } = useDecisions(queryStatus);
  const reviewDecision = useReviewDecision();

  if (isLoading) return <DecisionsSkeleton />;

  const pendingCount = decisions.filter((d) => d.status === "pending").length;

  return (
    <div className="@container/main mx-auto flex max-w-4xl flex-1 flex-col gap-6">
      {/* 헤더 */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">LLM 투자 결정</h1>
          <p className="text-sm text-muted-foreground">
            AI가 분석한 투자 결정을 검토하고 승인/거부합니다.
          </p>
        </div>
        {pendingCount > 0 && (
          <Badge className="border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
            {pendingCount}건 대기
          </Badge>
        )}
      </div>

      <Separator />

      {/* 필터 */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">상태:</span>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[140px]" aria-label="상태 필터">
            <SelectValue placeholder="전체" />
          </SelectTrigger>
          {/*
            position="popper": Next.js 16 + radix-ui 1.4 환경에서 기본값
            "item-aligned" 가 트리거 위치 매칭에 실패해 드롭다운이 열리지 않는
            현상이 있어 popper 로 고정한다.
          */}
          <SelectContent position="popper">
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* 결정 목록 */}
      <Card>
        <CardHeader className="border-b bg-muted/30 pb-3 pt-4">
          <div className="flex items-center gap-2">
            <BrainCircuit className="size-4 text-muted-foreground" />
            <CardTitle className="text-base">결정 목록</CardTitle>
          </div>
          <CardDescription>
            야간/장전/장후 AI 분석에서 생성된 투자 결정입니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          {decisions.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <BrainCircuit />
                </EmptyMedia>
                <EmptyTitle>결정이 없습니다</EmptyTitle>
                <EmptyDescription>
                  AI 야간/장전 분석 결과가 생성되면 이곳에 표시됩니다.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="space-y-3">
              {decisions.map((decision) => (
                <DecisionCard
                  key={decision.id}
                  decision={decision}
                  onApprove={() =>
                    reviewDecision.mutate({
                      id: decision.id,
                      action: "approve",
                    })
                  }
                  onReject={() =>
                    reviewDecision.mutate({
                      id: decision.id,
                      action: "reject",
                    })
                  }
                  isPending={reviewDecision.isPending}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
