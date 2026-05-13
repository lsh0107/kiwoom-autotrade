"use client";

import { useStrategyConfig } from "@/hooks/queries/use-strategy-config";
import { useStrategies } from "@/hooks/queries/use-strategies";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  MeanReversionStrategyFlow,
  MomentumStrategyFlow,
} from "@/components/strategy/strategy-flow";
import { TradeHistoryTable } from "@/components/bot/trade-history-table";

function ParamSummary({
  params,
}: {
  params: { label: string; value: string }[];
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {params.map((p) => (
        <Badge key={p.label} variant="secondary" className="text-xs font-normal">
          {p.label}:{" "}
          <span className="ml-1 font-mono font-semibold">{p.value}</span>
        </Badge>
      ))}
    </div>
  );
}

function StrategySkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-8 w-40" />
          <Skeleton className="mt-1 h-4 w-64" />
        </div>
        <Skeleton className="h-5 w-16" />
      </div>
      <Skeleton className="h-10 w-60" />
      <Skeleton className="h-40 w-full rounded-lg" />
      <Skeleton className="h-60 w-full rounded-lg" />
    </div>
  );
}

export default function StrategyPage() {
  const { data: configs = [], isLoading: configLoading } = useStrategyConfig();
  const { data: strategies = [], isLoading: strategiesLoading } = useStrategies();

  const isLoading = configLoading || strategiesLoading;
  if (isLoading) return <StrategySkeleton />;

  const configMap = Object.fromEntries(
    configs.map((c) => [c.key, c.value]),
  );

  const screenThreshold = Number(configMap.screen_threshold ?? 0.75);
  const volumeRatio = Number(configMap.volume_ratio ?? 0.3);
  const maxPositions = Number(configMap.max_positions ?? 3);
  const entryEndTime = String(configMap.entry_end_time ?? "13:00");
  const stopLoss = Math.abs(Number(configMap.stop_loss ?? 0.015));
  const takeProfit = Math.abs(Number(configMap.take_profit ?? 0.03));

  const momentumParams = [
    { label: "52주고 기준", value: `${(screenThreshold * 100).toFixed(0)}%` },
    { label: "거래량 배수", value: `${volumeRatio}x` },
    { label: "손절", value: `-${(stopLoss * 100).toFixed(1)}%` },
    { label: "익절", value: `+${(takeProfit * 100).toFixed(1)}%` },
    { label: "최대 포지션", value: String(maxPositions) },
    { label: "강제청산", value: entryEndTime },
  ];

  const activeCount = strategies.filter((s) => s.status === "active").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">전략 흐름</h1>
          <p className="text-sm text-muted-foreground">
            자동매매 전략 로직과 거래 이력을 확인합니다.
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          {activeCount > 0 ? `${activeCount}개 활성` : "비활성"}
        </Badge>
      </div>

      <Tabs defaultValue="momentum">
        <TabsList>
          <TabsTrigger value="momentum">모멘텀 돌파</TabsTrigger>
          <TabsTrigger value="mean_reversion">평균회귀</TabsTrigger>
        </TabsList>

        <TabsContent value="momentum" className="mt-4 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">파라미터</CardTitle>
              <CardDescription>
                현재 적용 중인 모멘텀 돌파 전략 설정값
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ParamSummary params={momentumParams} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">전략 흐름도</CardTitle>
              <CardDescription>
                진입 조건 → 보유 감시 → 청산 조건
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <MomentumStrategyFlow
                params={{
                  screenThreshold,
                  volumeRatio,
                  stopLossPct: stopLoss * 100,
                  takeProfitPct: takeProfit * 100,
                  entryEndTime,
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mean_reversion" className="mt-4 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">파라미터</CardTitle>
              <CardDescription>현재 활성 전략에서 미사용</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                현재 활성 전략(모멘텀 돌파)에서 평균회귀 파라미터는 사용되지 않습니다.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">전략 흐름도</CardTitle>
              <CardDescription>
                진입 조건 → 보유 감시 → 청산 조건
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <MeanReversionStrategyFlow />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Separator />

      {/* 거래 이력 — TradeHistoryTable 재사용 */}
      <TradeHistoryTable />
    </div>
  );
}
