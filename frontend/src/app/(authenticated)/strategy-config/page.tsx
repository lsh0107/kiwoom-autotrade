"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useStrategyConfig } from "@/hooks/queries/use-strategy-config";
import { useConfigSuggestions } from "@/hooks/queries/use-config-suggestions";
import { useKillSwitchStatus } from "@/hooks/queries/use-kill-switch-status";
import { useUpdateStrategyConfig } from "@/hooks/mutations/use-update-strategy-config";
import { useSoftStop } from "@/hooks/mutations/use-soft-stop";
import { useHardStop } from "@/hooks/mutations/use-hard-stop";
import { useResumeTrading } from "@/hooks/mutations/use-resume-trading";
import { useApproveSuggestion } from "@/hooks/mutations/use-approve-suggestion";
import type { KillSwitchStatus, StrategyConfigSuggestion } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  OctagonAlert,
  Play,
  Settings2,
  ShieldAlert,
  Lightbulb,
  ArrowRight,
} from "lucide-react";

/* ── Zod 스키마 — Input에서 문자열로 들어오므로 string으로 받아 숫자 검증 ── */
const numStr = (min: number, max: number) =>
  z
    .string()
    .min(1, "값을 입력하세요")
    .refine((v) => !isNaN(Number(v)), "숫자를 입력하세요")
    .refine((v) => Number(v) >= min, `최솟값: ${min}`)
    .refine((v) => Number(v) <= max, `최댓값: ${max}`);

const strategySchema = z.object({
  // 손절/익절
  atr_stop_mult: numStr(0.1, 10),
  atr_tp_mult: numStr(0.1, 10),
  stop_loss: numStr(0.001, 0.5),
  take_profit: numStr(0.001, 0.5),
  // 포지션
  max_positions: numStr(1, 100),
  max_holding_days: numStr(1, 365),
  gap_risk_threshold: numStr(0.001, 0.5),
  // 거래량
  volume_ratio: numStr(0.1, 100),
  // 시간
  entry_start_time: z.string().min(1, "시작 시간을 입력하세요"),
  entry_end_time: z.string().min(1, "종료 시간을 입력하세요"),
});

type StrategyFormValues = z.infer<typeof strategySchema>;

/* ── 카테고리 정의 ── */
const PARAM_CATEGORIES = [
  {
    label: "손절/익절",
    fields: [
      { key: "atr_stop_mult", label: "ATR 손절 배수" },
      { key: "atr_tp_mult", label: "ATR 익절 배수" },
      { key: "stop_loss", label: "고정 손절률 (양수 입력, 예: 0.015 = 1.5%)" },
      { key: "take_profit", label: "고정 익절률 (양수 입력, 예: 0.03 = 3%)" },
    ],
  },
  {
    label: "포지션",
    fields: [
      { key: "max_positions", label: "최대 보유 종목 수" },
      { key: "max_holding_days", label: "최대 보유 일수" },
      { key: "gap_risk_threshold", label: "갭 하락 손절 기준 (양수, 예: 0.03 = 3%)" },
    ],
  },
  {
    label: "거래량",
    fields: [{ key: "volume_ratio", label: "거래량 비율" }],
  },
  {
    label: "시간",
    fields: [
      { key: "entry_start_time", label: "진입 시작 시간" },
      { key: "entry_end_time", label: "진입 종료 시간" },
    ],
  },
] as const;

/* ── Kill Switch 상태 배지 ── */
function KillSwitchBadge({ status }: { status: KillSwitchStatus["status"] }) {
  if (status === "normal") {
    return (
      <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
        정상 운영
      </Badge>
    );
  }
  if (status === "soft_stopped") {
    return (
      <Badge className="border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
        Soft Stop
      </Badge>
    );
  }
  return (
    <Badge className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
      Hard Stop
    </Badge>
  );
}

/* ── Skeleton ── */
function StrategyConfigSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Skeleton className="h-8 w-32" />
        <Skeleton className="mt-1 h-4 w-56" />
      </div>
      <Skeleton className="h-px w-full" />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-28" />
        </CardHeader>
        <CardContent className="flex gap-3">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
        </CardContent>
      </Card>
      {Array.from({ length: 2 }).map((_, i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-20" />
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, j) => (
              <Skeleton key={j} className="h-9 w-full" />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/* ── 제안 카드 ── */
function SuggestionCard({
  suggestion,
  onApprove,
  onReject,
  isPending,
}: {
  suggestion: StrategyConfigSuggestion;
  onApprove: () => void;
  onReject: () => void;
  isPending: boolean;
}) {
  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{suggestion.config_key}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {suggestion.source}
          </p>
        </div>
        <Badge variant="outline" className="text-xs shrink-0">
          {suggestion.status}
        </Badge>
      </div>

      <div className="flex items-center gap-2 text-sm">
        <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs">
          {String(suggestion.current_value)}
        </span>
        <ArrowRight className="size-3 text-muted-foreground shrink-0" />
        <span className="rounded bg-emerald-50 px-2 py-0.5 font-mono text-xs text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
          {String(suggestion.suggested_value)}
        </span>
      </div>

      <p className="text-xs text-muted-foreground">{suggestion.reason}</p>

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
    </div>
  );
}

/* ── 메인 페이지 ── */
export default function StrategyConfigPage() {
  const { data: configs = [], isLoading: configLoading } = useStrategyConfig();
  const { data: suggestions = [], isLoading: suggestionsLoading } =
    useConfigSuggestions();
  const { data: killSwitchData, isLoading: killSwitchLoading } =
    useKillSwitchStatus();

  const updateConfig = useUpdateStrategyConfig();
  const softStop = useSoftStop();
  const hardStop = useHardStop();
  const resumeTrading = useResumeTrading();
  const approveSuggestion = useApproveSuggestion();

  // configs 배열을 key→value 객체로 변환
  const configMap = Object.fromEntries(
    configs.map((c) => [c.key, c.value])
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<StrategyFormValues>({
    resolver: zodResolver(strategySchema),
    values: {
      atr_stop_mult: String(configMap.atr_stop_mult ?? "2"),
      atr_tp_mult: String(configMap.atr_tp_mult ?? "3"),
      stop_loss: String(Math.abs(Number(configMap.stop_loss ?? 0.015))),
      take_profit: String(Math.abs(Number(configMap.take_profit ?? 0.03))),
      max_positions: String(configMap.max_positions ?? "5"),
      max_holding_days: String(configMap.max_holding_days ?? "20"),
      gap_risk_threshold: String(Math.abs(Number(configMap.gap_risk_threshold ?? 0.03))),
      volume_ratio: String(configMap.volume_ratio ?? "1.5"),
      entry_start_time: String(configMap.entry_start_time ?? "09:05"),
      entry_end_time: String(configMap.entry_end_time ?? "15:20"),
    },
  });

  const timeFields = new Set(["entry_start_time", "entry_end_time"]);

  const onSubmit = (values: StrategyFormValues) => {
    const descMap = Object.fromEntries(
      configs.map((c) => [c.key, c.description])
    );
    // 음수로 저장해야 하는 필드 (DB 규칙: 손절/갭은 음수)
    const negativeFields = new Set(["stop_loss", "gap_risk_threshold"]);
    const items = Object.entries(values).map(([key, raw]) => {
      let value: string | number = timeFields.has(key) ? raw : Number(raw);
      if (negativeFields.has(key) && typeof value === "number" && value > 0) {
        value = -value;
      }
      return { key, value, description: descMap[key] ?? "", updated_by: "user" };
    });
    updateConfig.mutate({ items });
  };

  const isLoading = configLoading || suggestionsLoading || killSwitchLoading;
  if (isLoading) return <StrategyConfigSkeleton />;

  const killStatus = killSwitchData?.status ?? "normal";
  const isStopped = killStatus !== "normal";

  return (
    <div className="@container/main mx-auto flex max-w-3xl flex-1 flex-col gap-6">
      {/* 페이지 헤더 */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">전략 설정</h1>
        <p className="text-sm text-muted-foreground">
          자동매매 파라미터 및 Kill Switch를 관리합니다.
        </p>
      </div>

      <Separator />

      {/* 섹션 1: Kill Switch 컨트롤 */}
      <Card>
        <CardHeader className="border-b bg-muted/30 pb-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="size-4 text-muted-foreground" />
            <CardTitle className="text-lg">Kill Switch</CardTitle>
          </div>
          <CardDescription>
            거래를 즉시 중단하거나 재개합니다. 현재 상태:{" "}
            <KillSwitchBadge status={killStatus} />
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3 pt-4">
          {/* Soft Stop */}
          <Button
            variant="outline"
            className="border-amber-200 text-amber-700 hover:bg-amber-50 dark:border-amber-800 dark:text-amber-300 dark:hover:bg-amber-950"
            onClick={() => softStop.mutate()}
            disabled={softStop.isPending || killStatus === "soft_stopped"}
          >
            <OctagonAlert className="mr-2 size-4" />
            Soft Stop
          </Button>

          {/* Hard Stop — AlertDialog 확인 */}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="destructive"
                disabled={hardStop.isPending || killStatus === "hard_stopped"}
              >
                <ShieldAlert className="mr-2 size-4" />
                Hard Stop
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent size="sm">
              <AlertDialogHeader>
                <AlertDialogTitle>Hard Stop 확인</AlertDialogTitle>
                <AlertDialogDescription>
                  모든 포지션이 즉시 청산됩니다. 실제 손실이 발생할 수 있습니다.
                  정말 실행하시겠습니까?
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>취소</AlertDialogCancel>
                <AlertDialogAction
                  variant="destructive"
                  onClick={() => hardStop.mutate()}
                >
                  실행
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {/* Resume — 중단 상태일 때만 표시 */}
          {isStopped && (
            <Button
              className="bg-emerald-600 text-white hover:bg-emerald-700 dark:bg-emerald-700 dark:hover:bg-emerald-800"
              onClick={() => resumeTrading.mutate()}
              disabled={resumeTrading.isPending}
            >
              <Play className="mr-2 size-4" />
              거래 재개
            </Button>
          )}
        </CardContent>
      </Card>

      {/* 섹션 2: 전략 파라미터 */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="flex items-center gap-2">
          <Settings2 className="size-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">전략 파라미터</h2>
        </div>

        {PARAM_CATEGORIES.map((category) => (
          <Card key={category.label}>
            <CardHeader className="border-b bg-muted/30 pb-3 pt-4">
              <CardTitle className="text-base">{category.label}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 pt-4 sm:grid-cols-2">
              {category.fields.map(({ key, label }) => {
                const error = errors[key as keyof StrategyFormValues];
                return (
                  <div key={key} className="space-y-1.5">
                    <Label htmlFor={key} className="text-sm">
                      {label}
                    </Label>
                    <Input
                      id={key}
                      type={timeFields.has(key) ? "time" : "text"}
                      {...register(key as keyof StrategyFormValues)}
                      placeholder={label}
                    />
                    {error && (
                      <p className="text-xs text-destructive">
                        {error.message}
                      </p>
                    )}
                    {configMap[key] !== undefined && (
                      <p className="text-xs text-muted-foreground">
                        현재:{" "}
                        {configs.find((c) => c.key === key)?.description ?? ""}
                      </p>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        ))}

        <div className="flex justify-end">
          <Button type="submit" disabled={updateConfig.isPending}>
            {updateConfig.isPending ? "저장 중..." : "파라미터 저장"}
          </Button>
        </div>
      </form>

      {/* 섹션 3: LLM 제안 */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Lightbulb className="size-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">LLM 파라미터 제안</h2>
        </div>

        <Card>
          <CardHeader className="border-b bg-muted/30 pb-3 pt-4">
            <CardTitle className="text-base">대기 중인 제안</CardTitle>
            <CardDescription>
              AI가 분석한 파라미터 조정 제안입니다. 검토 후 승인 또는 거부하세요.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            {suggestions.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Lightbulb />
                  </EmptyMedia>
                  <EmptyTitle>대기 중인 제안이 없습니다</EmptyTitle>
                  <EmptyDescription>
                    AI 분석 결과가 생성되면 이곳에 표시됩니다.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <div className="space-y-3">
                {suggestions.map((suggestion) => (
                  <SuggestionCard
                    key={suggestion.id}
                    suggestion={suggestion}
                    onApprove={() =>
                      approveSuggestion.mutate({
                        id: suggestion.id,
                        action: "approve",
                      })
                    }
                    onReject={() =>
                      approveSuggestion.mutate({
                        id: suggestion.id,
                        action: "reject",
                      })
                    }
                    isPending={approveSuggestion.isPending}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
