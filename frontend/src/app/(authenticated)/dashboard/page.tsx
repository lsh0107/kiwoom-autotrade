"use client";

import { useBalance } from "@/hooks/queries/use-balance";
import { ApiClientError } from "@/lib/api";
import { formatKRW, formatSignedKRW, formatSignedPercent } from "@/lib/format";
import type { AccountBalance } from "@/types/api";
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
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Wallet,
  PiggyBank,
  KeyRound,
  CircleDollarSign,
  Percent,
  Package,
} from "lucide-react";
import Link from "next/link";

/* ── Section Cards (dashboard-01 패턴) ── */
function SectionCards({ balance }: { balance: AccountBalance }) {
  const hasHoldings = balance.holdings.length > 0;

  const profitColor = !hasHoldings
    ? "text-muted-foreground"
    : balance.total_profit > 0
      ? "text-red-600 dark:text-red-400"
      : balance.total_profit < 0
        ? "text-blue-600 dark:text-blue-400"
        : "text-muted-foreground";

  const profitBg = !hasHoldings
    ? ""
    : balance.total_profit > 0
      ? "from-red-50/50 dark:from-red-950/20"
      : balance.total_profit < 0
        ? "from-blue-50/50 dark:from-blue-950/20"
        : "";

  return (
    <div className="grid gap-4 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
      {/* 총 평가금액 */}
      <Card className="@container/card">
        <CardHeader className="relative pb-0">
          <CardDescription className="flex items-center gap-1.5">
            <Wallet className="size-3.5" />
            총 평가금액
          </CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            ₩{formatKRW(balance.total_eval)}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="text-xs text-muted-foreground">
            예수금 + 평가금액 합산
          </div>
        </CardContent>
      </Card>

      {/* 주문가능금액 */}
      <Card className="@container/card">
        <CardHeader className="relative pb-0">
          <CardDescription className="flex items-center gap-1.5">
            <PiggyBank className="size-3.5" />
            주문가능금액
          </CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            ₩{formatKRW(balance.available_cash)}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="text-xs text-muted-foreground">
            현재 매수 가능한 금액
          </div>
        </CardContent>
      </Card>

      {/* 평가손익 */}
      <Card className={`@container/card bg-gradient-to-b ${profitBg}`}>
        <CardHeader className="relative pb-0">
          <CardDescription className="flex items-center gap-1.5">
            <CircleDollarSign className="size-3.5" />
            평가손익
          </CardDescription>
          <CardTitle
            className={`text-2xl font-semibold tabular-nums @[250px]/card:text-3xl ${profitColor}`}
          >
            {hasHoldings ? formatSignedKRW(balance.total_profit) : "—"}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="text-xs text-muted-foreground">
            {hasHoldings ? "전일 대비" : "보유종목 없음"}
          </div>
        </CardContent>
      </Card>

      {/* 수익률 */}
      <Card className={`@container/card bg-gradient-to-b ${profitBg}`}>
        <CardHeader className="relative pb-0">
          <CardDescription className="flex items-center gap-1.5">
            <Percent className="size-3.5" />
            수익률
          </CardDescription>
          <CardTitle
            className={`text-2xl font-semibold tabular-nums @[250px]/card:text-3xl ${profitColor}`}
          >
            {hasHoldings
              ? formatSignedPercent(balance.total_profit_pct)
              : "—"}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="text-xs text-muted-foreground">
            {hasHoldings ? "투자 원금 대비" : "보유종목 없음"}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* ── Skeleton Loading ── */
function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-32" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-0">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="mt-2 h-8 w-36" />
            </CardHeader>
            <CardContent className="pt-2">
              <Skeleton className="h-3 w-28" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-24" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

/* ── Holdings Table ── */
function HoldingsTable({ holdings }: { holdings: AccountBalance["holdings"] }) {
  if (!holdings.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Package />
          </EmptyMedia>
          <EmptyTitle>보유 종목이 없습니다</EmptyTitle>
          <EmptyDescription>
            매수 주문을 실행하면 보유 종목이 표시됩니다.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>종목</TableHead>
          <TableHead className="text-right">수량</TableHead>
          <TableHead className="text-right">평균가</TableHead>
          <TableHead className="text-right">현재가</TableHead>
          <TableHead className="text-right">평가금액</TableHead>
          <TableHead className="text-right">손익</TableHead>
          <TableHead className="text-right">수익률</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {holdings.map((h) => {
          const profitColor =
            h.profit > 0
              ? "text-red-600 dark:text-red-400"
              : h.profit < 0
                ? "text-blue-600 dark:text-blue-400"
                : "";
          return (
            <TableRow key={h.symbol} className="group">
              <TableCell>
                <div className="flex items-center gap-3">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-muted text-xs font-bold">
                    {h.name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-medium">{h.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {h.symbol}
                    </div>
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-right tabular-nums font-medium">
                {formatKRW(h.quantity)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                ₩{formatKRW(h.avg_price)}
              </TableCell>
              <TableCell className="text-right tabular-nums font-medium">
                ₩{formatKRW(h.current_price)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                ₩{formatKRW(h.eval_amount)}
              </TableCell>
              <TableCell
                className={`text-right tabular-nums font-medium ${profitColor}`}
              >
                {formatSignedKRW(h.profit)}
              </TableCell>
              <TableCell className="text-right">
                <Badge
                  variant="outline"
                  className={
                    h.profit_pct > 0
                      ? "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
                      : h.profit_pct < 0
                        ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300"
                        : ""
                  }
                >
                  {formatSignedPercent(h.profit_pct)}
                </Badge>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

/* ── 에러 상태 컴포넌트 ── */
function ErrorState({ error }: { error: string }) {
  const configs: Record<
    string,
    { title: string; desc: string; showLink: boolean }
  > = {
    no_credentials: {
      title: "API 키를 등록해주세요",
      desc: "키움증권 Open API 키를 등록하면 계좌 잔고와 보유종목을 조회할 수 있습니다.",
      showLink: true,
    },
    rate_limit: {
      title: "잠시 후 다시 시도해주세요",
      desc: "API 요청이 너무 많습니다. 잠시 기다린 후 페이지를 새로고침해주세요.",
      showLink: false,
    },
    broker_auth: {
      title: "API 키 인증 오류",
      desc: "키움 API 키가 만료되었거나 올바르지 않습니다. 설정에서 키를 다시 등록해주세요.",
      showLink: true,
    },
    unknown: {
      title: "잔고를 불러올 수 없습니다",
      desc: "일시적인 오류가 발생했습니다. 잠시 후 페이지를 새로고침해주세요.",
      showLink: false,
    },
  };
  const cfg = configs[error] ?? configs.unknown;

  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <KeyRound />
        </EmptyMedia>
        <EmptyTitle>{cfg.title}</EmptyTitle>
        <EmptyDescription>{cfg.desc}</EmptyDescription>
      </EmptyHeader>
      {cfg.showLink && (
        <EmptyContent>
          <Button asChild>
            <Link href="/settings">설정으로 이동</Link>
          </Button>
        </EmptyContent>
      )}
    </Empty>
  );
}

/** ApiClientError를 대시보드 에러 타입으로 변환 */
function resolveErrorType(err: unknown): string {
  if (err instanceof ApiClientError) {
    if (err.code === "BROKER_RATE_LIMIT") return "rate_limit";
    if (err.code === "BROKER_AUTH_ERROR") return "broker_auth";
    if (
      err.status === 404 ||
      err.code === "NOT_FOUND" ||
      err.code === "HTTP_404"
    )
      return "no_credentials";
  }
  return "unknown";
}

/* ── Main Page ── */
export default function DashboardPage() {
  const { data: balance, isLoading, error } = useBalance();

  if (isLoading) return <DashboardSkeleton />;

  return (
    <div className="@container/main flex flex-1 flex-col gap-4 md:gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">대시보드</h1>
          <p className="text-sm text-muted-foreground">
            계좌 현황 및 보유종목을 확인합니다.
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          모의투자
        </Badge>
      </div>

      <Separator />

      {error ? (
        <ErrorState error={resolveErrorType(error)} />
      ) : balance ? (
        <>
          <SectionCards balance={balance} />

          <Card className="overflow-hidden">
            <CardHeader className="border-b bg-muted/30">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">보유 종목</CardTitle>
                  <CardDescription>
                    {balance.holdings.length > 0
                      ? `${balance.holdings.length}개 종목 보유 중`
                      : "보유 종목 없음"}
                  </CardDescription>
                </div>
                {balance.holdings.length > 0 && (
                  <Badge variant="secondary">
                    {balance.holdings.length}종목
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <HoldingsTable holdings={balance.holdings} />
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
