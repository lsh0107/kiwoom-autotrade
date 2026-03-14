"use client";

import { useState } from "react";
import { useStrategies } from "@/hooks/queries/use-strategies";
import { useToggleStrategy } from "@/hooks/mutations/use-toggle-strategy";
import { useTradingStatus } from "@/hooks/queries/use-trading-status";
import { useKillSwitchStatus } from "@/hooks/queries/use-kill-switch-status";
import type { Strategy } from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Bot,
  Play,
  Square,
  ShieldAlert,
  Activity,
  CirclePause,
  Zap,
  Plus,
  Pencil,
} from "lucide-react";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { TradingStatusCard } from "@/components/bot/trading-status-card";
import { CreateStrategyDialog } from "@/components/bot/create-strategy-dialog";
import { EditStrategyDialog } from "@/components/bot/edit-strategy-dialog";
import { TradeHistoryTable } from "@/components/bot/trade-history-table";
import { LiveLogPanel } from "@/components/bot/live-log-panel";

function BotSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-9 w-32" />
      </div>
      <Separator />
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="mt-1 h-8 w-12" />
            </CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-24" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function StrategyStatusBadge({ status }: { status: Strategy["status"] }) {
  switch (status) {
    case "active":
      return (
        <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
          <Activity className="mr-1 size-3" />
          실행 중
        </Badge>
      );
    case "paused":
      return (
        <Badge className="border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          <CirclePause className="mr-1 size-3" />
          일시정지
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary">
          <Square className="mr-1 size-3" />
          중지
        </Badge>
      );
  }
}

function KillSwitchStatusBadge() {
  const { data: ksStatus } = useKillSwitchStatus();

  if (!ksStatus) return null;

  switch (ksStatus.status) {
    case "soft_stopped":
      return (
        <Badge className="border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-300">
          <ShieldAlert className="mr-1 size-3" />
          소프트 중지
        </Badge>
      );
    case "hard_stopped":
      return (
        <Badge className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          <ShieldAlert className="mr-1 size-3" />
          긴급 중지
        </Badge>
      );
    default:
      return (
        <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
          정상
        </Badge>
      );
  }
}

export default function BotPage() {
  const { data: strategies = [], isLoading } = useStrategies();
  const toggleStrategy = useToggleStrategy();
  const { data: tradingStatus } = useTradingStatus();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Strategy | null>(null);

  if (isLoading) return <BotSkeleton />;

  const activeCount = strategies.filter((s) => s.status === "active").length;
  const totalSymbols = new Set(strategies.flatMap((s) => s.symbols)).size;
  const isRunning = tradingStatus?.status === "running";

  return (
    <div className="@container/main flex flex-1 flex-col gap-4 md:gap-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">자동매매</h1>
          <p className="text-sm text-muted-foreground">
            전략 관리 및 트레이딩 프로세스를 제어합니다.
          </p>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => setCreateOpen(true)}
        >
          <Plus className="size-4" />
          전략 추가
        </Button>
      </div>

      <Separator />

      {/* 상태 카드 (2열) */}
      <div className="grid gap-4 sm:grid-cols-2">
        <TradingStatusCard />

        {/* Kill Switch 상태 요약 */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-muted-foreground" />
                <CardTitle className="text-lg">Kill Switch</CardTitle>
              </div>
              <KillSwitchStatusBadge />
            </div>
            <CardDescription>긴급 중지 제어 상태</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
              <span className="text-muted-foreground">활성 전략</span>
              <span className="tabular-nums">
                <span
                  className={
                    activeCount > 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : ""
                  }
                >
                  {activeCount}
                </span>
                / {strategies.length}
              </span>
              <span className="text-muted-foreground flex items-center gap-1">
                <Zap className="size-3" />
                감시 종목
              </span>
              <span className="tabular-nums">{totalSymbols}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 전략 테이블 */}
      <Card className="overflow-hidden">
        <CardHeader className="border-b bg-muted/30">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">전략 목록</CardTitle>
              <CardDescription>
                등록된 자동매매 전략을 관리합니다.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {strategies.length === 0 ? (
            <div className="p-6">
              <Empty>
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Bot />
                  </EmptyMedia>
                  <EmptyTitle>등록된 전략이 없습니다</EmptyTitle>
                  <EmptyDescription>
                    전략 추가 버튼을 눌러 자동매매 전략을 생성하세요.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>전략명</TableHead>
                  <TableHead>종목</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead className="text-right">제어</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {strategies.map((s) => (
                  <TableRow key={s.id} className="group">
                    <TableCell>
                      <div>
                        <div className="font-medium">{s.name}</div>
                        <div className="text-xs text-muted-foreground line-clamp-1">
                          {s.description}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {s.symbols.slice(0, 3).map((sym) => (
                          <Badge
                            key={sym}
                            variant="outline"
                            className="text-xs"
                          >
                            {sym}
                          </Badge>
                        ))}
                        {s.symbols.length > 3 && (
                          <Badge variant="secondary" className="text-xs">
                            +{s.symbols.length - 3}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <StrategyStatusBadge status={s.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => setEditTarget(s)}
                        >
                          <Pencil className="size-3.5" />
                          편집
                        </Button>
                        <Button
                          size="sm"
                          variant={
                            s.status === "active" ? "outline" : "default"
                          }
                          className="gap-1.5"
                          disabled={toggleStrategy.isPending}
                          onClick={() =>
                            toggleStrategy.mutate({
                              id: s.id,
                              status: s.status,
                            })
                          }
                        >
                          {s.status === "active" ? (
                            <>
                              <Square className="size-3.5" />
                              중지
                            </>
                          ) : (
                            <>
                              <Play className="size-3.5" />
                              시작
                            </>
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* 오늘 매매 이력 */}
      <TradeHistoryTable />

      {/* 실시간 로그 */}
      <LiveLogPanel isRunning={isRunning} />

      {/* 전략 생성/편집 다이얼로그 */}
      <CreateStrategyDialog open={createOpen} onOpenChange={setCreateOpen} />
      <EditStrategyDialog
        open={!!editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
        strategy={editTarget}
      />
    </div>
  );
}
