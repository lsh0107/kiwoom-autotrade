"use client";

import { useState } from "react";
import { api, ApiClientError } from "@/lib/api";
import type { Quote, Orderbook, CreateOrderRequest } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  Search,
  TrendingUp,
  TrendingDown,
  ArrowUpDown,
  ShoppingCart,
} from "lucide-react";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

function formatKRW(value: number) {
  return new Intl.NumberFormat("ko-KR").format(value);
}

/* ── Skeleton Loading ── */
function TradeSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {/* 현재가 스켈레톤 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-16" />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-9 w-40" />
          <Skeleton className="h-5 w-32" />
          <div className="grid grid-cols-2 gap-2 pt-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
      {/* 호가 스켈레톤 */}
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-5 w-12" />
        </CardHeader>
        <CardContent className="space-y-1.5">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-6 w-full" />
          ))}
        </CardContent>
      </Card>
      {/* 주문 스켈레톤 */}
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-5 w-12" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

export default function TradePage() {
  const [symbol, setSymbol] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [orderbook, setOrderbook] = useState<Orderbook | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);

  const [orderSide, setOrderSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [orderLoading, setOrderLoading] = useState(false);

  const searchSymbol = async () => {
    if (!symbol.trim()) return;
    setSearchLoading(true);
    try {
      const [q, ob] = await Promise.all([
        api.get<Quote>(`/api/v1/market/quote/${symbol}`),
        api.get<Orderbook>(`/api/v1/market/orderbook/${symbol}`),
      ]);
      setQuote(q);
      setOrderbook(ob);
      setPrice(String(q.price));
    } catch (err) {
      let msg = "종목을 찾을 수 없습니다.";
      if (err instanceof ApiClientError) {
        if (err.code === "NO_CREDENTIALS") {
          msg = "API 키가 등록되지 않았습니다. 설정에서 등록해주세요.";
        } else if (err.code === "BROKER_RATE_LIMIT") {
          msg = "API 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.";
        } else if (err.code === "BROKER_AUTH_ERROR") {
          msg = "키움 API 인증 오류. 설정에서 API 키를 확인해주세요.";
        } else if (err.code === "BROKER_ERROR") {
          msg = "잘못된 종목코드입니다. 6자리 숫자를 확인해주세요.";
        } else if (err.code === "NOT_FOUND" || err.status === 404) {
          msg = "종목을 찾을 수 없습니다. 종목코드를 확인해주세요.";
        } else {
          msg = err.message || "시세 조회 중 오류가 발생했습니다.";
        }
      }
      toast.error(msg);
      setQuote(null);
      setOrderbook(null);
    } finally {
      setSearchLoading(false);
    }
  };

  const submitOrder = async () => {
    if (!symbol || !quantity || !price) return;
    setOrderLoading(true);
    try {
      const req: CreateOrderRequest = {
        symbol,
        side: orderSide,
        price: Number(price),
        quantity: Number(quantity),
      };
      await api.post("/api/v1/orders", req);
      toast.success(`${orderSide === "BUY" ? "매수" : "매도"} 주문이 접수되었습니다.`);
      setQuantity("");
    } catch (err) {
      let msg = "주문에 실패했습니다.";
      if (err instanceof ApiClientError) {
        if (err.code === "BROKER_RATE_LIMIT") {
          msg = "API 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.";
        } else {
          msg = err.message || "주문 처리 중 오류가 발생했습니다.";
        }
      }
      toast.error(msg);
    } finally {
      setOrderLoading(false);
    }
  };

  // 호가 잔량 최대값 (바 차트 비율 계산용)
  const maxQuantity =
    orderbook
      ? Math.max(
          ...orderbook.asks.map((a) => a.quantity),
          ...orderbook.bids.map((b) => b.quantity),
          1,
        )
      : 1;

  const changeColor =
    quote && quote.change >= 0
      ? "text-red-600 dark:text-red-400"
      : "text-blue-600 dark:text-blue-400";

  const changeBg =
    quote && quote.change >= 0
      ? "from-red-50/50 dark:from-red-950/20"
      : "from-blue-50/50 dark:from-blue-950/20";

  return (
    <div className="@container/main flex flex-1 flex-col gap-4 md:gap-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">트레이딩</h1>
          <p className="text-sm text-muted-foreground">
            종목 시세 조회 및 매매 주문을 실행합니다.
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          모의투자
        </Badge>
      </div>

      <Separator />

      {/* 종목 검색 */}
      <div className="flex gap-2">
        <Input
          placeholder="종목코드 (예: 005930)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !searchLoading && searchSymbol()}
          className="max-w-xs"
        />
        <Button onClick={searchSymbol} disabled={searchLoading}>
          <Search className="mr-2 size-4" />
          {searchLoading ? "검색 중..." : "조회"}
        </Button>
      </div>

      {/* 로딩 스켈레톤 */}
      {searchLoading && <TradeSkeleton />}

      {/* 빈 상태 */}
      {!quote && !searchLoading && (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Search />
            </EmptyMedia>
            <EmptyTitle>종목을 검색하세요</EmptyTitle>
            <EmptyDescription>
              종목코드를 입력하면 현재가, 호가, 주문을 할 수 있습니다.
              예: 005930 (삼성전자), 000660 (SK하이닉스)
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {quote && !searchLoading && (
        <div className="grid gap-4 lg:grid-cols-3">
          {/* 현재가 */}
          <Card className={`@container/card bg-gradient-to-b ${changeBg}`}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{quote.name}</CardTitle>
                <Badge variant="outline">{quote.symbol}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold tabular-nums @[250px]/card:text-4xl">
                  ₩{formatKRW(quote.price)}
                </span>
                {quote.change >= 0 ? (
                  <TrendingUp className="size-5 text-red-600 dark:text-red-400" />
                ) : (
                  <TrendingDown className="size-5 text-blue-600 dark:text-blue-400" />
                )}
              </div>
              <div className={`flex items-center gap-2 text-sm font-medium ${changeColor}`}>
                <span className="tabular-nums">
                  {quote.change >= 0 ? "+" : ""}
                  {formatKRW(quote.change)}
                </span>
                <Badge
                  variant="outline"
                  className={
                    quote.change >= 0
                      ? "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
                      : "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300"
                  }
                >
                  {quote.change_pct >= 0 ? "+" : ""}
                  {quote.change_pct.toFixed(2)}%
                </Badge>
              </div>
              <Separator className="my-2" />
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">시가</span>
                  <span className="tabular-nums">₩{formatKRW(quote.open)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">고가</span>
                  <span className="tabular-nums text-red-600 dark:text-red-400">
                    ₩{formatKRW(quote.high)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">저가</span>
                  <span className="tabular-nums text-blue-600 dark:text-blue-400">
                    ₩{formatKRW(quote.low)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">거래량</span>
                  <span className="tabular-nums">{formatKRW(quote.volume)}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 호가창 */}
          <Card className="overflow-hidden">
            <CardHeader className="border-b bg-muted/30 pb-2">
              <div className="flex items-center gap-2">
                <ArrowUpDown className="size-4 text-muted-foreground" />
                <CardTitle className="text-lg">호가</CardTitle>
              </div>
              <CardDescription>클릭하면 주문 가격에 반영됩니다</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {orderbook && (
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-[30%] text-right text-blue-600 dark:text-blue-400">
                        매도잔량
                      </TableHead>
                      <TableHead className="w-[40%] text-center">가격</TableHead>
                      <TableHead className="w-[30%] text-red-600 dark:text-red-400">
                        매수잔량
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {orderbook.asks
                      .slice()
                      .reverse()
                      .map((ask, i) => {
                        const barWidth = (ask.quantity / maxQuantity) * 100;
                        return (
                          <TableRow
                            key={`ask-${i}`}
                            className="relative hover:bg-blue-50/50 dark:hover:bg-blue-950/30"
                          >
                            <TableCell className="relative text-right tabular-nums font-medium text-blue-600 dark:text-blue-400">
                              <div
                                className="absolute inset-y-0 right-0 bg-blue-100/60 dark:bg-blue-900/30"
                                style={{ width: `${barWidth}%` }}
                              />
                              <span className="relative">{formatKRW(ask.quantity)}</span>
                            </TableCell>
                            <TableCell
                              className="cursor-pointer text-center font-mono tabular-nums transition-colors hover:bg-blue-100 hover:font-bold dark:hover:bg-blue-900/50"
                              onClick={() => {
                                setPrice(String(ask.price));
                                toast.info(`가격 ${formatKRW(ask.price)}원 설정`);
                              }}
                            >
                              {formatKRW(ask.price)}
                            </TableCell>
                            <TableCell />
                          </TableRow>
                        );
                      })}
                    {orderbook.bids.map((bid, i) => {
                      const barWidth = (bid.quantity / maxQuantity) * 100;
                      return (
                        <TableRow
                          key={`bid-${i}`}
                          className="relative hover:bg-red-50/50 dark:hover:bg-red-950/30"
                        >
                          <TableCell />
                          <TableCell
                            className="cursor-pointer text-center font-mono tabular-nums transition-colors hover:bg-red-100 hover:font-bold dark:hover:bg-red-900/50"
                            onClick={() => {
                              setPrice(String(bid.price));
                              toast.info(`가격 ${formatKRW(bid.price)}원 설정`);
                            }}
                          >
                            {formatKRW(bid.price)}
                          </TableCell>
                          <TableCell className="relative tabular-nums font-medium text-red-600 dark:text-red-400">
                            <div
                              className="absolute inset-y-0 left-0 bg-red-100/60 dark:bg-red-900/30"
                              style={{ width: `${barWidth}%` }}
                            />
                            <span className="relative">{formatKRW(bid.quantity)}</span>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* 주문 폼 */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <ShoppingCart className="size-4 text-muted-foreground" />
                <CardTitle className="text-lg">주문</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Tabs
                value={orderSide}
                onValueChange={(v) => setOrderSide(v as "BUY" | "SELL")}
              >
                <TabsList className="w-full">
                  <TabsTrigger
                    value="BUY"
                    className="flex-1 data-[state=active]:bg-red-600 data-[state=active]:text-white dark:data-[state=active]:bg-red-700"
                  >
                    매수
                  </TabsTrigger>
                  <TabsTrigger
                    value="SELL"
                    className="flex-1 data-[state=active]:bg-blue-600 data-[state=active]:text-white dark:data-[state=active]:bg-blue-700"
                  >
                    매도
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              <div
                className={`rounded-lg border p-3 ${
                  orderSide === "BUY"
                    ? "border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20"
                    : "border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/20"
                }`}
              >
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">가격</Label>
                    <Input
                      type="number"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      placeholder="주문 가격"
                      className="bg-background tabular-nums"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">수량</Label>
                    <Input
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      placeholder="주문 수량"
                      min={1}
                      className="bg-background tabular-nums"
                    />
                  </div>
                </div>
              </div>

              {price && quantity && (
                <div className="rounded-lg bg-muted/50 p-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">주문 금액</span>
                    <span className="text-lg font-bold tabular-nums">
                      ₩{formatKRW(Number(price) * Number(quantity))}
                    </span>
                  </div>
                </div>
              )}

              <Button
                className={`w-full ${
                  orderSide === "BUY"
                    ? "bg-red-600 text-white hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-800"
                    : "bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800"
                }`}
                onClick={submitOrder}
                disabled={orderLoading || !quantity || !price}
              >
                {orderLoading
                  ? "주문 중..."
                  : `${orderSide === "BUY" ? "매수" : "매도"} 주문`}
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
