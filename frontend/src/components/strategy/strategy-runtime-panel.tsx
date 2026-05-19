"use client";

import { useState } from "react";
import { useStrategyRuntime } from "@/hooks/queries/use-strategy-runtime";
import { useUpdateStrategyRuntime } from "@/hooks/mutations/use-update-strategy-runtime";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import { formatKRW } from "@/lib/format";
import type { StrategyRuntimeView } from "@/types/api";

/** 전략 런타임 토글 + budget 패널 (design-025) */
export function StrategyRuntimePanel() {
  const { data, isLoading, error } = useStrategyRuntime();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>전략 토글 + 자산 분배</CardTitle>
          <CardDescription>로딩 중…</CardDescription>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-24" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>전략 토글 + 자산 분배</CardTitle>
          <CardDescription className="text-destructive">조회 실패</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const totalEnabledBudget = data
    .filter((row) => row.enabled)
    .reduce((acc, row) => acc + row.budget_pct, 0);
  const totalPct = Math.round(totalEnabledBudget * 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle>전략 토글 + 자산 분배</CardTitle>
        <CardDescription>
          enabled 전략의 budget 합계: <strong>{totalPct}%</strong> / 100%
          {totalPct < 100 && (
            <span className="ml-2 text-muted-foreground">
              여유 현금 {100 - totalPct}%
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {data.map((row) => (
          <StrategyRow key={row.id} row={row} />
        ))}
      </CardContent>
    </Card>
  );
}

function StrategyRow({ row }: { row: StrategyRuntimeView }) {
  const update = useUpdateStrategyRuntime();
  const [budgetPct, setBudgetPct] = useState(row.budget_pct);
  const [maxOrderAmount, setMaxOrderAmount] = useState(row.max_order_amount);
  const isPending = update.isPending;

  const onToggle = (checked: boolean) => {
    update.mutate({ strategy: row.strategy, enabled: checked });
  };

  const onSaveBudget = () => {
    if (budgetPct === row.budget_pct && maxOrderAmount === row.max_order_amount) {
      return;
    }
    update.mutate({
      strategy: row.strategy,
      budget_pct: budgetPct,
      max_order_amount: maxOrderAmount,
    });
  };

  return (
    <div className="rounded border p-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold">{row.strategy}</span>
            <Badge variant={row.enabled ? "default" : "secondary"}>
              {row.enabled ? "ENABLED" : "DISABLED"}
            </Badge>
          </div>
          <div className="text-xs text-muted-foreground">
            최근 갱신: {new Date(row.updated_at).toLocaleString("ko-KR")} {row.updated_by && `· ${row.updated_by}`}
          </div>
        </div>
        <Switch
          checked={row.enabled}
          onCheckedChange={onToggle}
          disabled={isPending}
          aria-label={`${row.strategy} 활성/비활성`}
        />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <label className="text-sm">
          <span className="block text-muted-foreground">budget_pct (0~1)</span>
          <Input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={budgetPct}
            onChange={(e) => setBudgetPct(Number(e.target.value))}
            disabled={isPending}
          />
        </label>
        <label className="text-sm">
          <span className="block text-muted-foreground">
            max_order_amount ({formatKRW(maxOrderAmount)})
          </span>
          <Input
            type="number"
            min={0}
            step={100_000}
            value={maxOrderAmount}
            onChange={(e) => setMaxOrderAmount(Number(e.target.value))}
            disabled={isPending}
          />
        </label>
      </div>
      <div className="mt-2 flex justify-end">
        <Button
          size="sm"
          variant="outline"
          onClick={onSaveBudget}
          disabled={isPending}
        >
          {isPending && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
          저장
        </Button>
      </div>
    </div>
  );
}
