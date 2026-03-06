"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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
import { TrendingUp, TrendingDown, Wallet, PiggyBank, KeyRound } from "lucide-react";
import Link from "next/link";

function formatKRW(value: number) {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function ProfitBadge({ rate }: { rate: number }) {
  if (rate > 0)
    return <Badge variant="destructive">+{rate.toFixed(2)}%</Badge>;
  if (rate < 0) return <Badge variant="secondary">{rate.toFixed(2)}%</Badge>;
  return <Badge variant="outline">0.00%</Badge>;
}

export default function DashboardPage() {
  const [balance, setBalance] = useState<AccountBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await api.get<AccountBalance>("/api/v1/account/balance");
        setBalance(data);
      } catch {
        setError("데이터를 불러올 수 없습니다. 키움 API 키를 설정해주세요.");
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
      <h1 className="text-2xl font-bold">대시보드</h1>

      {error ? (
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
      ) : (
        <>
          {/* 요약 카드 */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">총 평가금액</CardTitle>
                <Wallet className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {balance ? `₩${formatKRW(balance.total_eval)}` : "-"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">주문가능금액</CardTitle>
                <PiggyBank className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {balance ? `₩${formatKRW(balance.available_cash)}` : "-"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">평가손익</CardTitle>
                {balance && balance.total_profit >= 0 ? (
                  <TrendingUp className="size-4 text-red-500" />
                ) : (
                  <TrendingDown className="size-4 text-blue-500" />
                )}
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {balance ? `₩${formatKRW(balance.total_profit)}` : "-"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">수익률</CardTitle>
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
              <CardTitle>보유 종목</CardTitle>
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
                        <TableCell className="text-right">
                          {formatKRW(h.quantity)}
                        </TableCell>
                        <TableCell className="text-right">
                          ₩{formatKRW(h.avg_price)}
                        </TableCell>
                        <TableCell className="text-right">
                          ₩{formatKRW(h.current_price)}
                        </TableCell>
                        <TableCell className="text-right">
                          ₩{formatKRW(h.eval_amount)}
                        </TableCell>
                        <TableCell className="text-right">
                          ₩{formatKRW(h.profit)}
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
