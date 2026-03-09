"use client";

import { useEffect, useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import type { AccountBalance } from "@/types/api";
import {
  Card,
  CardContent,
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
import { Spinner } from "@/components/ui/spinner";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  PiggyBank,
  KeyRound,
  BarChart3,
  CircleDollarSign,
} from "lucide-react";
import Link from "next/link";

function formatKRW(value: number) {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function ProfitBadge({ rate }: { rate: number }) {
  if (rate > 0)
    return (
      <Badge className="bg-red-500/10 text-red-600 border-red-200 hover:bg-red-500/20">
        +{rate.toFixed(2)}%
      </Badge>
    );
  if (rate < 0)
    return (
      <Badge className="bg-blue-500/10 text-blue-600 border-blue-200 hover:bg-blue-500/20">
        {rate.toFixed(2)}%
      </Badge>
    );
  return <Badge variant="outline">0.00%</Badge>;
}

function ProfitText({ value, prefix = "" }: { value: number; prefix?: string }) {
  const color = value > 0 ? "text-red-600" : value < 0 ? "text-blue-600" : "";
  const sign = value > 0 ? "+" : "";
  return (
    <span className={color}>
      {sign}{prefix}{formatKRW(value)}
    </span>
  );
}

export default function DashboardPage() {
  const [balance, setBalance] = useState<AccountBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"no_credentials" | "rate_limit" | "broker_auth" | "unknown" | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await api.get<AccountBalance>("/api/v1/account/balance");
        setBalance(data);
      } catch (err) {
        if (err instanceof ApiClientError) {
          if (err.code === "BROKER_RATE_LIMIT") {
            setError("rate_limit");
          } else if (err.code === "BROKER_AUTH_ERROR") {
            setError("broker_auth");
          } else if (err.status === 404 || err.code === "NOT_FOUND" || err.code === "HTTP_404") {
            setError("no_credentials");
          } else {
            setError("unknown");
          }
        } else {
          setError("unknown");
        }
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner className="size-6" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">대시보드</h1>
      </div>

      {error === "no_credentials" ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <KeyRound />
            </EmptyMedia>
            <EmptyTitle>API 키를 등록해주세요</EmptyTitle>
            <EmptyDescription>
              키움증권 Open API 키를 등록하면 계좌 잔고와 보유종목을 조회할 수 있습니다.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button asChild>
              <Link href="/settings">설정으로 이동</Link>
            </Button>
          </EmptyContent>
        </Empty>
      ) : error === "rate_limit" ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <KeyRound />
            </EmptyMedia>
            <EmptyTitle>잠시 후 다시 시도해주세요</EmptyTitle>
            <EmptyDescription>
              API 요청이 너무 많습니다. 잠시 기다린 후 페이지를 새로고침해주세요.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : error === "broker_auth" ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <KeyRound />
            </EmptyMedia>
            <EmptyTitle>API 키 인증 오류</EmptyTitle>
            <EmptyDescription>
              키움 API 키가 만료되었거나 올바르지 않습니다. 설정에서 키를 다시 등록해주세요.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button asChild>
              <Link href="/settings">설정으로 이동</Link>
            </Button>
          </EmptyContent>
        </Empty>
      ) : error === "unknown" ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <KeyRound />
            </EmptyMedia>
            <EmptyTitle>잔고를 불러올 수 없습니다</EmptyTitle>
            <EmptyDescription>
              일시적인 오류가 발생했습니다. 잠시 후 페이지를 새로고침해주세요.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <>
          {/* 요약 카드 */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  총 평가금액
                </CardTitle>
                <Wallet className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {balance ? `₩${formatKRW(balance.total_eval)}` : "-"}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  주문가능금액
                </CardTitle>
                <PiggyBank className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {balance ? `₩${formatKRW(balance.available_cash)}` : "-"}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  평가손익
                </CardTitle>
                <CircleDollarSign className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {balance ? (
                    <ProfitText value={balance.total_profit} prefix="₩" />
                  ) : "-"}
                </div>
                {balance && (
                  <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                    {balance.total_profit >= 0 ? (
                      <TrendingUp className="size-3 text-red-500" />
                    ) : (
                      <TrendingDown className="size-3 text-blue-500" />
                    )}
                    <span>전일 대비</span>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  수익률
                </CardTitle>
                <BarChart3 className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {balance ? (
                    <ProfitBadge rate={balance.total_profit_pct} />
                  ) : (
                    "-"
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 보유종목 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">보유 종목</CardTitle>
            </CardHeader>
            <CardContent>
              {!balance?.holdings.length ? (
                <Empty>
                  <EmptyHeader>
                    <EmptyTitle>보유 종목이 없습니다</EmptyTitle>
                    <EmptyDescription>
                      현재 보유 중인 종목이 없습니다.
                    </EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
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
                    {balance.holdings.map((h) => (
                      <TableRow key={h.symbol}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{h.name}</div>
                            <div className="text-xs text-muted-foreground">
                              {h.symbol}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatKRW(h.quantity)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          ₩{formatKRW(h.avg_price)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          ₩{formatKRW(h.current_price)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          ₩{formatKRW(h.eval_amount)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          <ProfitText value={h.profit} prefix="₩" />
                        </TableCell>
                        <TableCell className="text-right">
                          <ProfitBadge rate={h.profit_pct} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
