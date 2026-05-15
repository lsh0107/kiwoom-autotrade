"use client";

import { useMemo } from "react";
import { useShortSwingCandidates } from "@/hooks/queries/use-short-swing-candidates";
import { useShortSwingPositions } from "@/hooks/queries/use-short-swing-positions";
import { formatKRW } from "@/lib/format";
import type { ShortSwingDetail } from "@/types/api";
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  data: ShortSwingDetail;
}

/** 오늘 날짜를 YYYY-MM-DD 형식으로 반환 */
function todayDateStr(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function ShortSwingDashboard({ data }: Props) {
  const today = useMemo(() => todayDateStr(), []);
  const { data: candidatesRes, isLoading: candidatesLoading } =
    useShortSwingCandidates(today);
  const { data: positionsRes, isLoading: positionsLoading } =
    useShortSwingPositions("open");

  const candidates = candidatesRes?.candidates ?? [];
  const positions = positionsRes?.positions ?? [];

  return (
    <div className="space-y-4">
      {/* 전략 파라미터 그리드 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* 1. 전략명 + 보유기간 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              전략
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">Short Swing</p>
            <p className="mt-1 text-xs text-muted-foreground">
              보유기간: 2~10거래일
            </p>
          </CardContent>
        </Card>

        {/* 2. 진입/청산 시간 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              매매 시간
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>
              신규 진입:{" "}
              <span className="font-semibold">{data.entry_window}</span>
            </p>
            <p>
              청산:{" "}
              <span className="font-semibold">{data.exit_window}</span>
            </p>
          </CardContent>
        </Card>

        {/* 3. 포지션 설정 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              포지션
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>
              최대 보유:{" "}
              <span className="font-semibold">{data.max_positions}종목</span>
            </p>
            <p>
              하루 신규:{" "}
              <span className="font-semibold">
                {data.max_daily_new_positions}종목
              </span>
            </p>
            <p>
              현재:{" "}
              <span className="font-semibold">
                {data.open_positions}/{data.max_positions}
              </span>
              {data.today_new_positions > 0 && (
                <span className="ml-1 text-xs text-muted-foreground">
                  (오늘 +{data.today_new_positions})
                </span>
              )}
            </p>
          </CardContent>
        </Card>

        {/* 4. 손익 설정 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              손익 설정
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>
              손절:{" "}
              <span className="font-semibold text-blue-600">
                {(data.stop_loss * 100).toFixed(1)}%
              </span>
            </p>
            <p>
              익절:{" "}
              <span className="font-semibold text-red-600">
                +{(data.take_profit * 100).toFixed(1)}%
              </span>
            </p>
            <p>
              트레일링:{" "}
              <span className="font-semibold">
                +{(data.trailing_armed_pct * 100).toFixed(1)}% 이후 고점 대비{" "}
                {(data.trailing_stop_pct * 100).toFixed(1)}%
              </span>
            </p>
          </CardContent>
        </Card>

        {/* 5. 보유/유니버스 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              보유 및 유니버스
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>
              최대 보유일:{" "}
              <span className="font-semibold">
                {data.max_holding_days}거래일
              </span>
            </p>
            <p>
              유니버스:{" "}
              <span className="font-semibold">{data.universe_size}종목</span>
            </p>
            <p>
              최소 주문:{" "}
              <span className="font-mono text-xs">
                ₩{formatKRW(data.min_order_amount)}
              </span>
            </p>
          </CardContent>
        </Card>

        {/* 6. 다음 후보 생성 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              후보 생성
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">
              {data.next_candidate_screen_at}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              다음 후보 스크리닝 예정 시각
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 현재 보유 포지션 */}
      <Card className="overflow-hidden">
        <CardHeader className="border-b bg-muted/30">
          <CardTitle className="text-lg">보유 포지션</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {positionsLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : positions.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              보유 포지션이 없습니다
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>종목</TableHead>
                  <TableHead className="text-right">진입가</TableHead>
                  <TableHead className="text-right">수량</TableHead>
                  <TableHead className="text-right">손절가</TableHead>
                  <TableHead className="text-right">익절가</TableHead>
                  <TableHead>트레일링</TableHead>
                  <TableHead>보유 만기</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {positions.map((pos) => (
                  <TableRow key={pos.id}>
                    <TableCell>
                      <div>
                        <span className="font-mono text-sm">{pos.symbol}</span>
                        <span className="ml-1.5 text-xs text-muted-foreground">
                          {pos.name}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        진입: {pos.entry_date}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      ₩{formatKRW(pos.entry_price)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {pos.quantity}주
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-blue-600">
                      ₩{formatKRW(pos.stop_price)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-red-600">
                      ₩{formatKRW(pos.take_profit_price)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={pos.trailing_armed ? "default" : "secondary"}
                      >
                        {pos.trailing_armed ? "활성" : "대기"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {pos.max_holding_until}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* 오늘 후보 리스트 */}
      <Card className="overflow-hidden">
        <CardHeader className="border-b bg-muted/30">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">오늘 후보 종목</CardTitle>
            {candidatesRes && (
              <Badge variant="outline" className="text-xs">
                {candidatesRes.date} · {candidatesRes.count}종목
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {candidatesLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : candidates.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              오늘 후보 종목이 없습니다 (다음 스크리닝:{" "}
              {data.next_candidate_screen_at})
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>종목</TableHead>
                  <TableHead className="text-right">종가</TableHead>
                  <TableHead className="text-right">고점 대비</TableHead>
                  <TableHead className="text-right">5일 수익률</TableHead>
                  <TableHead className="text-right">점수</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {candidates.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <span className="font-mono text-sm">{c.symbol}</span>
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        {c.name}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      ₩{formatKRW(c.close)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-blue-600">
                      {(c.drawdown_from_high * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell
                      className={`text-right tabular-nums ${
                        c.return_5d >= 0 ? "text-red-600" : "text-blue-600"
                      }`}
                    >
                      {c.return_5d >= 0 ? "+" : ""}
                      {(c.return_5d * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right tabular-nums font-semibold">
                      {c.score.toFixed(2)}
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
