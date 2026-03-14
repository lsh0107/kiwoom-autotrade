"use client";

import { useTradeHistory } from "@/hooks/queries/use-trade-history";
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
import { Skeleton } from "@/components/ui/skeleton";
import { formatKRW, formatDate } from "@/lib/format";
import { History } from "lucide-react";

/** 당일 매매 이력 테이블 */
export function TradeHistoryTable() {
  const { data: history = [], isLoading } = useTradeHistory();

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <History className="size-4 text-muted-foreground" />
          <CardTitle className="text-lg">오늘 매매 이력</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : history.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            오늘 매매 이력이 없습니다
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>시각</TableHead>
                <TableHead>종목</TableHead>
                <TableHead>구분</TableHead>
                <TableHead className="text-right">가격</TableHead>
                <TableHead className="text-right">수량</TableHead>
                <TableHead>메시지</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="tabular-nums text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(item.created_at).slice(11)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-sm">{item.symbol}</span>
                      {item.is_mock && (
                        <Badge variant="secondary" className="text-xs px-1">
                          모의
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {item.side === "BUY" ? (
                      <Badge className="border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
                        매수
                      </Badge>
                    ) : (
                      <Badge className="border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300">
                        매도
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    ₩{formatKRW(item.price)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatKRW(item.quantity)}주
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                    {item.message}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
