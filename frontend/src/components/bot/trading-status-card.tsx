"use client";

import { useState } from "react";
import { useTradingStatus } from "@/hooks/queries/use-trading-status";
import { useStartTrading } from "@/hooks/mutations/use-start-trading";
import { useStopTrading } from "@/hooks/mutations/use-stop-trading";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Play, Square, Activity, Clock } from "lucide-react";
import type { TradingStatus } from "@/types/api";

function StatusBadge({ status }: { status: TradingStatus["status"] }) {
  switch (status) {
    case "running":
      return (
        <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
          <span className="mr-1.5 size-1.5 animate-pulse rounded-full bg-emerald-500 inline-block" />
          실행 중
        </Badge>
      );
    case "starting":
      return (
        <Badge className="border-yellow-200 bg-yellow-50 text-yellow-700 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-300">
          시작 중
        </Badge>
      );
    case "stopping":
      return (
        <Badge className="border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-300">
          중지 중
        </Badge>
      );
    case "crashed":
      return (
        <Badge className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          오류
        </Badge>
      );
    default:
      return <Badge variant="secondary">대기</Badge>;
  }
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600)
    return `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}시간 ${m}분`;
}

/** 트레이딩 프로세스 상태 카드 */
export function TradingStatusCard() {
  const { data: status } = useTradingStatus();
  const startTrading = useStartTrading();
  const stopTrading = useStopTrading();
  const [stopDialogOpen, setStopDialogOpen] = useState(false);

  const isRunning = status?.status === "running";
  const isTransitioning =
    status?.status === "starting" || status?.status === "stopping";

  return (
    <>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-muted-foreground" />
              <CardTitle className="text-lg">트레이딩 프로세스</CardTitle>
            </div>
            <StatusBadge status={status?.status ?? "idle"} />
          </div>
          <CardDescription>자동매매 프로세스 제어</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
            <span className="text-muted-foreground">PID</span>
            <span className="tabular-nums">{status?.pid ?? "-"}</span>
            {status?.started_at && (
              <>
                <span className="text-muted-foreground">시작 시각</span>
                <span className="tabular-nums text-xs">
                  {new Date(status.started_at).toLocaleTimeString("ko-KR")}
                </span>
              </>
            )}
            {isRunning && status?.uptime_seconds !== undefined && (
              <>
                <span className="text-muted-foreground flex items-center gap-1">
                  <Clock className="size-3" />
                  업타임
                </span>
                <span className="tabular-nums">
                  {formatUptime(status.uptime_seconds)}
                </span>
              </>
            )}
          </div>

          <div className="flex gap-2 pt-1">
            {!isRunning && (
              <Button
                size="sm"
                className="gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700"
                disabled={
                  startTrading.isPending ||
                  isTransitioning ||
                  status?.status === "crashed"
                }
                onClick={() => startTrading.mutate()}
              >
                <Play className="size-3.5" />
                시작
              </Button>
            )}
            {isRunning && (
              <Button
                size="sm"
                variant="destructive"
                className="gap-1.5"
                disabled={stopTrading.isPending || isTransitioning}
                onClick={() => setStopDialogOpen(true)}
              >
                <Square className="size-3.5" />
                중지
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={stopDialogOpen} onOpenChange={setStopDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>프로세스 중지 확인</AlertDialogTitle>
            <AlertDialogDescription>
              자동매매 프로세스를 중지합니다. 진행 중인 주문은 완료 후
              중지됩니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                stopTrading.mutate();
                setStopDialogOpen(false);
              }}
            >
              중지
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
