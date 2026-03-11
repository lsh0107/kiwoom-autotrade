"use client";

import { Badge } from "@/components/ui/badge";
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
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  MeanReversionStrategyFlow,
  MomentumStrategyFlow,
} from "@/components/strategy/strategy-flow";
import { Workflow } from "lucide-react";

interface TradeRecord {
  date: string;
  symbol: string;
  name: string;
  strategy: "momentum" | "mean_reversion";
  side: "BUY" | "SELL";
  price: number;
  pnl: number | null;
  exitReason?: string;
}

const mockTrades: TradeRecord[] = [];

const momentumParams = [
  { label: "52주고 기준", value: "70%" },
  { label: "거래량 배수", value: "0.5x" },
  { label: "손절", value: "-0.5%" },
  { label: "익절", value: "+1.0%" },
  { label: "최대 포지션", value: "5" },
  { label: "강제청산", value: "14:30" },
];

const meanReversionParams = [
  { label: "RSI 과매도", value: "<40" },
  { label: "RSI 과매수", value: ">70" },
  { label: "BB 표준편차", value: "1.5σ" },
  { label: "거래량 배수", value: "0.8x" },
  { label: "손절", value: "-1.5%" },
  { label: "익절", value: "+1.5%" },
];

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

export default function StrategyPage() {
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
          2개 전략
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
              <MomentumStrategyFlow />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mean_reversion" className="mt-4 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">파라미터</CardTitle>
              <CardDescription>현재 적용 중인 평균회귀 전략 설정값</CardDescription>
            </CardHeader>
            <CardContent>
              <ParamSummary params={meanReversionParams} />
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

      {/* 거래 이력 */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">최근 거래 이력</h2>
          <Badge variant="outline" className="text-xs">
            {mockTrades.length}건
          </Badge>
        </div>

        {mockTrades.length === 0 ? (
          <Empty className="border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Workflow />
              </EmptyMedia>
              <EmptyTitle>아직 거래 기록이 없습니다</EmptyTitle>
              <EmptyDescription>
                전략이 실행되면 거래 이력이 여기에 표시됩니다.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Card className="overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>날짜</TableHead>
                  <TableHead>종목</TableHead>
                  <TableHead>전략</TableHead>
                  <TableHead>구분</TableHead>
                  <TableHead className="text-right">가격</TableHead>
                  <TableHead className="text-right">수익률</TableHead>
                  <TableHead>청산 사유</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mockTrades.map((trade, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs text-muted-foreground">
                      {trade.date}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-xs font-medium">{trade.name}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {trade.symbol}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {trade.strategy === "momentum" ? "모멘텀" : "평균회귀"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          trade.side === "BUY"
                            ? "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
                            : "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300"
                        }
                      >
                        {trade.side === "BUY" ? "매수" : "매도"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {trade.price.toLocaleString()}원
                    </TableCell>
                    <TableCell className="text-right">
                      {trade.pnl === null ? (
                        <span className="text-xs text-muted-foreground">-</span>
                      ) : (
                        <span
                          className={`font-mono text-xs font-semibold ${
                            trade.pnl > 0
                              ? "text-red-600 dark:text-red-400"
                              : trade.pnl < 0
                                ? "text-blue-600 dark:text-blue-400"
                                : ""
                          }`}
                        >
                          {trade.pnl > 0 ? "+" : ""}
                          {trade.pnl.toFixed(2)}%
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="text-xs text-muted-foreground">
                        {trade.exitReason ?? "-"}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
}
