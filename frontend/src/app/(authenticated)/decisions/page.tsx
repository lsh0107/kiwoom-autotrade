"use client";

import { useState } from "react";
import { useDecisions } from "@/hooks/queries/use-decisions";
import { useReviewDecision } from "@/hooks/mutations/use-review-decision";
import type { LLMDecision } from "@/types/api";
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
};

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

      {/* 내용 요약 */}
      <div className="rounded-md bg-muted/50 p-3 text-xs space-y-1">
        {Object.entries(content).map(([key, value]) => (
          <div key={key} className="flex gap-2">
            <span className="font-medium text-muted-foreground min-w-[80px]">
              {key}:
            </span>
            <span className="font-mono break-all">
              {typeof value === "object" ? JSON.stringify(value) : String(value)}
            </span>
          </div>
        ))}
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
