"use client";

import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
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
import { toast } from "sonner";
import {
  Bot,
  Play,
  Square,
  ShieldAlert,
  Activity,
  CirclePause,
  Zap,
} from "lucide-react";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

function BotSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-9 w-32" />
      </div>
      <Separator />
      <div className="grid gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
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

function StatusBadge({ status }: { status: Strategy["status"] }) {
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

export default function BotPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await api.get<Strategy[]>("/api/v1/bot/strategies");
        setStrategies(data);
      } catch {
        // API 미연동 시 빈 목록
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, []);

  const toggleStrategy = async (id: string, status: string) => {
    try {
      const action = status === "active" ? "stop" : "start";
      await api.post(`/api/v1/bot/strategies/${id}/${action}`);
      setStrategies((prev) =>
        prev.map((s) =>
          s.id === id
            ? { ...s, status: status === "active" ? "stopped" : "active" }
            : s,
        ),
      );
      toast.success(
        status === "active"
          ? "전략이 중지되었습니다."
          : "전략이 시작되었습니다.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiClientError ? err.message : "실패했습니다.";
      toast.error(msg);
    }
  };

  const killSwitch = async () => {
    if (!confirm("모든 자동매매를 긴급 중지합니다. 계속하시겠습니까?")) return;
    try {
      await api.post("/api/v1/bot/kill-switch", { active: true });
      setStrategies((prev) =>
        prev.map((s) => ({ ...s, status: "stopped" as const })),
      );
      toast.success("Kill Switch 발동 — 모든 전략이 중지되었습니다.");
    } catch (err) {
      const msg =
        err instanceof ApiClientError ? err.message : "Kill Switch 실패";
      toast.error(msg);
    }
  };

  if (loading) return <BotSkeleton />;

  const activeCount = strategies.filter((s) => s.status === "active").length;
  const totalSymbols = new Set(strategies.flatMap((s) => s.symbols)).size;

  return (
    <div className="@container/main flex flex-1 flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">자동매매</h1>
          <p className="text-sm text-muted-foreground">
            전략 관리 및 킬스위치를 제어합니다.
          </p>
        </div>
        <Button
          variant="destructive"
          size="sm"
          onClick={killSwitch}
          className="gap-1.5"
        >
          <ShieldAlert className="size-4" />
          Kill Switch
        </Button>
      </div>

      <Separator />

      {/* 요약 카드 */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-0">
            <CardDescription className="flex items-center gap-1.5">
              <Bot className="size-3.5" />
              등록 전략
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {strategies.length}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="text-xs text-muted-foreground">전체 등록된 전략 수</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-0">
            <CardDescription className="flex items-center gap-1.5">
              <Zap className="size-3.5" />
              실행 중
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              <span
                className={
                  activeCount > 0
                    ? "text-emerald-600 dark:text-emerald-400"
                    : ""
                }
              >
                {activeCount}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="text-xs text-muted-foreground">현재 활성 전략 수</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-0">
            <CardDescription className="flex items-center gap-1.5">
              <Activity className="size-3.5" />
              감시 종목
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums">
              {totalSymbols}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="text-xs text-muted-foreground">전략에 등록된 고유 종목</div>
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
                    자동매매 전략을 생성하면 AI가 자동으로 매수/매도 판단을
                    합니다.
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
                      <StatusBadge status={s.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant={s.status === "active" ? "outline" : "default"}
                        className="gap-1.5"
                        onClick={() => toggleStrategy(s.id, s.status)}
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
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
