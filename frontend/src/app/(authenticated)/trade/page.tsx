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
import { toast } from "sonner";
import { Search } from "lucide-react";
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">트레이딩</h1>

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

      {quote && (
        <div className="grid gap-4 lg:grid-cols-3">
          {/* 현재가 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{quote.name}</span>
                <Badge variant="outline">{quote.symbol}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="text-3xl font-bold">₩{formatKRW(quote.price)}</div>
              <div
                className={
                  quote.change >= 0 ? "text-red-500" : "text-blue-500"
                }
              >
                {quote.change >= 0 ? "+" : ""}
                {formatKRW(quote.change)} ({quote.change_pct >= 0 ? "+" : ""}
                {quote.change_pct.toFixed(2)}%)
              </div>
              <div className="grid grid-cols-2 gap-2 pt-2 text-sm text-muted-foreground">
                <div>시가 ₩{formatKRW(quote.open)}</div>
                <div>고가 ₩{formatKRW(quote.high)}</div>
                <div>저가 ₩{formatKRW(quote.low)}</div>
                <div>거래량 {formatKRW(quote.volume)}</div>
              </div>
            </CardContent>
          </Card>

          {/* 호가창 */}
          <Card>
            <CardHeader>
              <CardTitle>호가</CardTitle>
            </CardHeader>
            <CardContent>
              {orderbook && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-right">매도잔량</TableHead>
                      <TableHead className="text-center">가격</TableHead>
                      <TableHead>매수잔량</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {orderbook.asks
                      .slice()
                      .reverse()
                      .map((ask, i) => (
                        <TableRow key={`ask-${i}`}>
                          <TableCell className="text-right text-blue-500">
                            {formatKRW(ask.quantity)}
                          </TableCell>
                          <TableCell
                            className="cursor-pointer text-center font-mono hover:underline"
                            onClick={() => setPrice(String(ask.price))}
                          >
                            {formatKRW(ask.price)}
                          </TableCell>
                          <TableCell />
                        </TableRow>
                      ))}
                    {orderbook.bids.map((bid, i) => (
                      <TableRow key={`bid-${i}`}>
                        <TableCell />
                        <TableCell
                          className="cursor-pointer text-center font-mono hover:underline"
                          onClick={() => setPrice(String(bid.price))}
                        >
                          {formatKRW(bid.price)}
                        </TableCell>
                        <TableCell className="text-red-500">
                          {formatKRW(bid.quantity)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* 주문 폼 */}
          <Card>
            <CardHeader>
              <CardTitle>주문</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Tabs
                value={orderSide}
                onValueChange={(v) => setOrderSide(v as "BUY" | "SELL")}
              >
                <TabsList className="w-full">
                  <TabsTrigger value="BUY" className="flex-1">
                    매수
                  </TabsTrigger>
                  <TabsTrigger value="SELL" className="flex-1">
                    매도
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              <div className="space-y-2">
                <Label>가격</Label>
                <Input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="주문 가격"
                />
              </div>

              <div className="space-y-2">
                <Label>수량</Label>
                <Input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  placeholder="주문 수량"
                  min={1}
                />
              </div>

              {price && quantity && (
                <div className="text-sm text-muted-foreground">
                  주문 금액: ₩{formatKRW(Number(price) * Number(quantity))}
                </div>
              )}

              <Button
                className="w-full"
                variant={orderSide === "BUY" ? "destructive" : "default"}
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
