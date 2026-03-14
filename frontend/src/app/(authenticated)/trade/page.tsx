"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRealtime } from "@/hooks/use-realtime";
import { useQuote } from "@/hooks/queries/use-quote";
import { useOrderbook } from "@/hooks/queries/use-orderbook";
import { useDailyChart } from "@/hooks/queries/use-daily-chart";
import { usePlaceOrder } from "@/hooks/mutations/use-place-order";
import { PriceChart } from "@/components/charts/price-chart";
import { ApiClientError } from "@/lib/api";
import { formatKRW } from "@/lib/format";
import { getErrorMessage } from "@/lib/errors";
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

/* ── 주문 폼 Zod 스키마 ── */
const orderSchema = z.object({
  price: z.number().int("가격은 정수만 가능합니다").positive("가격을 입력해주세요"),
  quantity: z.number().int().positive("수량을 입력해주세요"),
});
type OrderFormValues = z.infer<typeof orderSchema>;

/* ── Skeleton Loading ── */
function TradeSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
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
  const [inputSymbol, setInputSymbol] = useState("");
  const [searchSymbol, setSearchSymbol] = useState("");
  const [orderSide, setOrderSide] = useState<"BUY" | "SELL">("BUY");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pendingOrder = useRef<OrderFormValues | null>(null);

  const realtimeSymbols = useMemo(
    () => (searchSymbol ? [searchSymbol] : []),
    [searchSymbol],
  );
  const { ticks, isConnected } = useRealtime(realtimeSymbols);
  const liveTick = ticks.get(searchSymbol);

  const quoteQuery = useQuote(searchSymbol);
  const orderbookQuery = useOrderbook(searchSymbol);
  const chartQuery = useDailyChart(searchSymbol);
  const placeOrder = usePlaceOrder();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<OrderFormValues>({
    resolver: zodResolver(orderSchema),
    defaultValues: { price: 0, quantity: 0 },
  });

  const priceValue = watch("price");
  const quantityValue = watch("quantity");

  // 새 종목 검색 성공 시 현재가를 주문 가격에 자동 설정
  useEffect(() => {
    if (quoteQuery.data) {
      setValue("price", quoteQuery.data.price);
    }
  }, [quoteQuery.data, setValue]);

  // 조회 에러 시 토스트 표시
  useEffect(() => {
    const err = quoteQuery.error;
    if (!err) return;
    const msg =
      err instanceof ApiClientError
        ? getErrorMessage(err.code, err.message)
        : "종목을 찾을 수 없습니다.";
    toast.error(msg);
  }, [quoteQuery.error]);

  const handleSearch = () => {
    if (!inputSymbol.trim()) return;
    setSearchSymbol(inputSymbol.trim());
  };

  const onSubmit = (values: OrderFormValues) => {
    if (!searchSymbol) return;
    pendingOrder.current = values;
    setConfirmOpen(true);
  };

  const executeOrder = () => {
    const values = pendingOrder.current;
    if (!values || !searchSymbol) return;
    placeOrder.mutate(
      {
        symbol: searchSymbol,
        side: orderSide,
        price: values.price,
        quantity: values.quantity,
      },
      {
        onSuccess: () => {
          reset({ price: quoteQuery.data?.price ?? 0, quantity: 0 });
        },
      },
    );
    pendingOrder.current = null;
  };

  const isSearching = quoteQuery.isFetching || orderbookQuery.isFetching;
  const quote = quoteQuery.data;
  const orderbook = orderbookQuery.data;

  // 호가 잔량 최대값 (바 차트 비율 계산용)
  const maxQuantity = orderbook
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
          value={inputSymbol}
          onChange={(e) => setInputSymbol(e.target.value)}
          onKeyDown={(e) =>
            e.key === "Enter" && !isSearching && handleSearch()
          }
          className="max-w-xs"
        />
        <Button onClick={handleSearch} disabled={isSearching}>
          <Search className="mr-2 size-4" />
          {isSearching ? "검색 중..." : "조회"}
        </Button>
      </div>

      {/* 로딩 스켈레톤 */}
      {isSearching && <TradeSkeleton />}

      {/* 빈 상태 */}
      {!quote && !isSearching && (
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

      {/* 주문 확인 다이얼로그 */}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {orderSide === "BUY" ? "매수" : "매도"} 주문 확인
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>아래 내용으로 주문을 실행합니다.</p>
                <div className="rounded-lg border bg-muted/50 p-3 text-sm">
                  <div className="grid grid-cols-2 gap-1.5">
                    <span className="text-muted-foreground">종목</span>
                    <span className="font-medium text-foreground">
                      {quote?.name} ({searchSymbol})
                    </span>
                    <span className="text-muted-foreground">구분</span>
                    <span
                      className={`font-bold ${orderSide === "BUY" ? "text-red-600" : "text-blue-600"}`}
                    >
                      {orderSide === "BUY" ? "매수" : "매도"}
                    </span>
                    <span className="text-muted-foreground">가격</span>
                    <span className="font-medium tabular-nums text-foreground">
                      ₩{formatKRW(pendingOrder.current?.price ?? 0)}
                    </span>
                    <span className="text-muted-foreground">수량</span>
                    <span className="font-medium tabular-nums text-foreground">
                      {formatKRW(pendingOrder.current?.quantity ?? 0)}주
                    </span>
                    <span className="text-muted-foreground">총 금액</span>
                    <span className="font-bold tabular-nums text-foreground">
                      ₩
                      {formatKRW(
                        (pendingOrder.current?.price ?? 0) *
                          (pendingOrder.current?.quantity ?? 0),
                      )}
                    </span>
                  </div>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={executeOrder}
              className={
                orderSide === "BUY"
                  ? "bg-red-600 text-white hover:bg-red-700"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              }
            >
              {orderSide === "BUY" ? "매수" : "매도"} 실행
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 캔들차트 */}
      {searchSymbol && chartQuery.data && chartQuery.data.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              {quote?.name ?? searchSymbol} 일봉 차트
            </CardTitle>
          </CardHeader>
          <CardContent>
            <PriceChart data={chartQuery.data} />
          </CardContent>
        </Card>
      )}
      {searchSymbol && chartQuery.isLoading && (
        <Card>
          <CardContent className="py-4">
            <Skeleton className="h-[350px] w-full" />
          </CardContent>
        </Card>
      )}

      {quote && !isSearching && (
        <div className="grid gap-4 lg:grid-cols-3">
          {/* 현재가 */}
          <Card className={`@container/card bg-gradient-to-b ${changeBg}`}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{quote.name}</CardTitle>
                <div className="flex items-center gap-2">
                  {isConnected && (
                    <div className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400">
                      <span className="size-1.5 animate-pulse rounded-full bg-green-500" />
                      실시간
                    </div>
                  )}
                  <Badge variant="outline">{quote.symbol}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold tabular-nums @[250px]/card:text-4xl">
                  ₩{formatKRW(liveTick?.price ?? quote.price)}
                </span>
                {quote.change >= 0 ? (
                  <TrendingUp className="size-5 text-red-600 dark:text-red-400" />
                ) : (
                  <TrendingDown className="size-5 text-blue-600 dark:text-blue-400" />
                )}
              </div>
              <div
                className={`flex items-center gap-2 text-sm font-medium ${changeColor}`}
              >
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
                  <span className="tabular-nums">
                    {formatKRW(quote.volume)}
                  </span>
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
                      <TableHead className="w-[40%] text-center">
                        가격
                      </TableHead>
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
                              <span className="relative">
                                {formatKRW(ask.quantity)}
                              </span>
                            </TableCell>
                            <TableCell
                              className="cursor-pointer text-center font-mono tabular-nums transition-colors hover:bg-blue-100 hover:font-bold dark:hover:bg-blue-900/50"
                              onClick={() => {
                                setValue("price", ask.price);
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
                              setValue("price", bid.price);
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
                            <span className="relative">
                              {formatKRW(bid.quantity)}
                            </span>
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

              <form onSubmit={handleSubmit(onSubmit)}>
                <div
                  className={`rounded-lg border p-3 ${
                    orderSide === "BUY"
                      ? "border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20"
                      : "border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/20"
                  }`}
                >
                  <div className="space-y-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">
                        가격
                      </Label>
                      <Input
                        type="number"
                        step="1"
                        {...register("price", { valueAsNumber: true })}
                        placeholder="주문 가격"
                        className="bg-background tabular-nums"
                      />
                      {errors.price && (
                        <p className="text-xs text-destructive">
                          {errors.price.message}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">
                        수량
                      </Label>
                      <Input
                        type="number"
                        {...register("quantity", { valueAsNumber: true })}
                        placeholder="주문 수량"
                        min={1}
                        className="bg-background tabular-nums"
                      />
                      {errors.quantity && (
                        <p className="text-xs text-destructive">
                          {errors.quantity.message}
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {priceValue > 0 && quantityValue > 0 && (
                  <div className="mt-3 rounded-lg bg-muted/50 p-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">주문 금액</span>
                      <span className="text-lg font-bold tabular-nums">
                        ₩{formatKRW(priceValue * quantityValue)}
                      </span>
                    </div>
                  </div>
                )}

                <Button
                  type="submit"
                  className={`mt-4 w-full ${
                    orderSide === "BUY"
                      ? "bg-red-600 text-white hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-800"
                      : "bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800"
                  }`}
                  disabled={placeOrder.isPending}
                >
                  {placeOrder.isPending
                    ? "주문 중..."
                    : `${orderSide === "BUY" ? "매수" : "매도"} 주문`}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
