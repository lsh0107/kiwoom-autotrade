"use client";

import { useResults } from "@/hooks/queries/use-results";
import { formatDate } from "@/lib/format";
import type { BacktestResult, BacktestResultItem } from "@/types/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { Progress } from "@/components/ui/progress";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Bar, BarChart, XAxis, YAxis } from "recharts";
import {
  BarChart3,
  Calendar,
  Target,
  TrendingUp,
  TrendingDown,
  AlertCircle,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

function MetricValue({
  value,
  suffix = "",
  colored = false,
}: {
  value: number;
  suffix?: string;
  colored?: boolean;
}) {
  const color = colored
    ? value > 0
      ? "text-red-600"
      : value < 0
        ? "text-blue-600"
        : ""
    : "";
  return (
    <span className={`font-mono text-sm font-semibold tabular-nums ${color}`}>
      {value.toFixed(2)}
      {suffix}
    </span>
  );
}

function ResultCard({
  result,
  runAt,
}: {
  result: BacktestResult;
  runAt: string;
}) {
  const validResults = (result.results ?? []).filter(
    (
      r,
    ): r is BacktestResultItem & {
      metrics: NonNullable<BacktestResultItem["metrics"]>;
    } => !!r.metrics && !r.error,
  );
  const errorResults = (result.results ?? []).filter((r) => r.error);

  const chartConfig: ChartConfig = {
    win_rate: { label: "승률", color: "var(--chart-1)" },
  };

  const chartData = validResults.map((r) => ({
    symbol: r.symbol,
    win_rate: r.metrics.win_rate * 100,
    total_trades: r.metrics.total_trades,
  }));

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base font-semibold">
              백테스트 결과
            </CardTitle>
            <CardDescription className="flex items-center gap-2 text-xs">
              <Calendar className="size-3" />
              {formatDate(runAt)}
              <span className="text-muted-foreground">
                | {result.trading_dates?.length ?? 0}일간
              </span>
            </CardDescription>
          </div>
          <div className="flex gap-1.5">
            {(result.symbols ?? []).map((s) => (
              <Badge key={s} variant="outline" className="text-xs">
                {s}
              </Badge>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 파라미터 */}
        <div className="flex flex-wrap gap-2">
          {Object.entries(result.params ?? {}).map(([key, val]) => (
            <Badge key={key} variant="secondary" className="text-xs font-normal">
              {key}: {val}
            </Badge>
          ))}
        </div>

        <Separator />

        {/* 종목별 결과 */}
        {validResults.length > 0 && (
          <div className="grid gap-3 md:grid-cols-2">
            {/* 메트릭스 카드 */}
            <div className="space-y-3">
              {validResults.map((r) => (
                <div
                  key={r.symbol}
                  className="space-y-2 rounded-lg border p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{r.symbol}</span>
                    <Badge variant="outline" className="text-xs">
                      {r.metrics.total_trades}건
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">승률</span>
                      <MetricValue
                        value={r.metrics.win_rate * 100}
                        suffix="%"
                      />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">평균 PnL</span>
                      <MetricValue
                        value={r.metrics.avg_pnl * 100}
                        suffix="%"
                        colored
                      />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">MDD</span>
                      <MetricValue
                        value={r.metrics.max_drawdown * 100}
                        suffix="%"
                        colored
                      />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">샤프</span>
                      <MetricValue value={r.metrics.sharpe_ratio} />
                    </div>
                  </div>
                  {r.metrics.total_trades > 0 && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>승: {r.metrics.win_count}</span>
                        <span>패: {r.metrics.loss_count}</span>
                      </div>
                      <Progress
                        value={r.metrics.win_rate * 100}
                        className="h-1.5"
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* 차트 */}
            {chartData.length > 0 &&
              chartData.some((d) => d.total_trades > 0) && (
                <div className="rounded-lg border p-3">
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    종목별 승률
                  </p>
                  <ChartContainer
                    config={chartConfig}
                    className="aspect-[4/3]"
                  >
                    <BarChart data={chartData}>
                      <XAxis
                        dataKey="symbol"
                        tickLine={false}
                        axisLine={false}
                        fontSize={11}
                      />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        fontSize={11}
                        tickFormatter={(v: number) => `${v}%`}
                        domain={[0, 100]}
                      />
                      <ChartTooltip
                        content={
                          <ChartTooltipContent
                            formatter={(value) => [`${value}%`, "승률"]}
                          />
                        }
                      />
                      <Bar
                        dataKey="win_rate"
                        fill="var(--color-win_rate)"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ChartContainer>
                </div>
              )}
          </div>
        )}

        {/* 에러 결과 */}
        {errorResults.length > 0 && (
          <div className="space-y-1.5">
            {errorResults.map((r) => (
              <div
                key={r.symbol}
                className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs"
              >
                <AlertCircle className="size-3.5 shrink-0 text-amber-500" />
                <span className="font-medium">{r.symbol}</span>
                <span className="text-muted-foreground">{r.error}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ResultsPage() {
  const { data, isLoading } = useResults();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner className="size-6" />
      </div>
    );
  }

  const fileList = data?.fileList ?? [];
  const resultsMap = data?.resultsMap ?? new Map();
  const allResults = Array.from(resultsMap.entries());

  const withTrades = allResults.filter(([, r]) =>
    Array.isArray(r.results) &&
    r.results.some(
      (item: BacktestResultItem) => item.metrics && !item.error,
    ),
  );
  const withErrors = allResults.filter(([, r]) =>
    Array.isArray(r.results) &&
    r.results.every((item: BacktestResultItem) => item.error),
  );

  const totalRuns = fileList.length;
  const successRuns = withTrades.length;
  const totalTrades = withTrades.reduce(
    (acc, [, r]) =>
      acc +
      (r.results ?? []).reduce(
        (sum: number, item: BacktestResultItem) =>
          sum + (item.metrics?.total_trades ?? 0),
        0,
      ),
    0,
  );
  const avgWinRate =
    withTrades.length > 0
      ? withTrades.reduce((acc, [, r]) => {
          const validItems = (r.results ?? []).filter(
            (item: BacktestResultItem) =>
              item.metrics && item.metrics.total_trades > 0,
          );
          if (validItems.length === 0) return acc;
          const avg =
            validItems.reduce(
              (s: number, item: BacktestResultItem) =>
                s + (item.metrics?.win_rate ?? 0),
              0,
            ) / validItems.length;
          return acc + avg;
        }, 0) /
          withTrades.filter(([, r]) =>
            (r.results ?? []).some(
              (item: BacktestResultItem) =>
                item.metrics && item.metrics.total_trades > 0,
            ),
          ).length || 0
      : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">매매 결과</h1>
        <Badge variant="outline" className="text-xs">
          총 {totalRuns}건
        </Badge>
      </div>

      {/* 요약 카드 */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              백테스트 실행
            </CardTitle>
            <BarChart3 className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalRuns}건</div>
            <p className="mt-1 text-xs text-muted-foreground">
              성공 {successRuns} / 에러 {withErrors.length}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              총 거래 수
            </CardTitle>
            <Target className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalTrades}건</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              평균 승률
            </CardTitle>
            {avgWinRate >= 0.5 ? (
              <TrendingUp className="size-4 text-red-500" />
            ) : (
              <TrendingDown className="size-4 text-blue-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(avgWinRate * 100).toFixed(1)}%
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 결과 목록 */}
      {allResults.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <BarChart3 />
            </EmptyMedia>
            <EmptyTitle>매매 결과가 없습니다</EmptyTitle>
            <EmptyDescription>
              백테스트를 실행하면 결과가 여기에 표시됩니다.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <ScrollArea className="h-[calc(100vh-320px)]">
          <div className="space-y-4 pr-4">
            {allResults.map(([filename, result]) => (
              <ResultCard
                key={filename}
                result={result}
                runAt={result.run_at}
              />
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
