"use client";

import type { CrossMomentumDetail } from "@/types/api";
import { formatKRW, formatRebalanceDate } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface Props {
  data: CrossMomentumDetail;
}

export function CrossMomentumDashboard({ data }: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {/* 1. 수식 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            수식
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg font-semibold">{data.formula}</p>
        </CardContent>
      </Card>

      {/* 2. Universe */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            유니버스
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg font-semibold">{data.universe_size}종목</p>
          <p className="mt-1 text-xs text-muted-foreground">
            KOSPI200 + KOSDAQ100 frozen list
          </p>
        </CardContent>
      </Card>

      {/* 3. Filters */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            필터
          </CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Badge variant={data.use_vol_filter ? "default" : "secondary"}>
            변동성 {data.use_vol_filter ? "ON" : "OFF"}
          </Badge>
          <Badge variant={data.use_trend_filter ? "default" : "secondary"}>
            추세 {data.use_trend_filter ? "ON" : "OFF"}
          </Badge>
        </CardContent>
      </Card>

      {/* 4. Schedule */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            리밸런싱 일정
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg font-semibold">
            {data.rebalance_freq === "monthly" ? "월간" : data.rebalance_freq}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            다음:{" "}
            {data.next_rebalance_kst
              ? formatRebalanceDate(data.next_rebalance_kst)
              : "—"}
          </p>
        </CardContent>
      </Card>

      {/* 5. Sizing */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            포지션 설정
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            종목 수: <span className="font-semibold">{data.n_positions}</span>
          </p>
          <p>
            현금 버퍼:{" "}
            <span className="font-semibold">
              {(data.cash_buffer_pct * 100).toFixed(0)}%
            </span>
          </p>
          <p>
            주문 범위:{" "}
            <span className="font-mono text-xs">
              {formatKRW(data.min_order_amount)} ~ {formatKRW(data.max_order_amount)}원
            </span>
          </p>
        </CardContent>
      </Card>

      {/* 6. Expected orders */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            예상 주문
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.target_preview.length > 0 || data.expected_orders ? (
            <div className="space-y-2">
              {data.target_preview.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {data.target_preview.map((symbol) => (
                    <Badge key={symbol} variant="outline" className="text-xs">
                      {symbol}
                    </Badge>
                  ))}
                </div>
              )}
              {data.expected_orders && (
                <div className="space-y-1 text-sm">
                  <p>
                    매도 {data.expected_orders.sells.length}건 / 매수{" "}
                    {data.expected_orders.buys.length}건
                  </p>
                  <p className="text-xs text-muted-foreground">
                    총 예상 금액: {formatKRW(data.expected_orders.total_notional)}원
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              다음 trigger 시점에 계산됩니다
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
