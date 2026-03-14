"use client";

import { useEffect, useRef, useState } from "react";
import { useTradingLogs } from "@/hooks/queries/use-trading-logs";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, Terminal } from "lucide-react";

interface LiveLogPanelProps {
  /** 프로세스가 running 상태일 때만 폴링 활성화 */
  isRunning: boolean;
}

/** 실시간 로그 패널 (접이식) */
export function LiveLogPanel({ isRunning }: LiveLogPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const { data: logs } = useTradingLogs(isRunning && expanded);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 새 로그 수신 시 자동 스크롤
  useEffect(() => {
    if (expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, expanded]);

  if (!isRunning) return null;

  const allLines = [
    ...(logs?.stdout ?? []).map((l) => ({ type: "out" as const, line: l })),
    ...(logs?.stderr ?? []).map((l) => ({ type: "err" as const, line: l })),
  ];

  return (
    <Card>
      <CardHeader className="border-b bg-muted/30 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="size-4 text-muted-foreground" />
            <CardTitle className="text-base">실시간 로그</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1"
            onClick={() => setExpanded((prev) => !prev)}
          >
            {expanded ? (
              <>
                <ChevronUp className="size-4" />
                접기
              </>
            ) : (
              <>
                <ChevronDown className="size-4" />
                펼치기
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="p-0">
          <div
            ref={scrollRef}
            className="h-64 overflow-y-auto bg-black p-3 font-mono text-xs"
          >
            {allLines.length === 0 ? (
              <span className="text-gray-500">로그 없음</span>
            ) : (
              allLines.map((entry, i) => (
                <div
                  key={i}
                  className={
                    entry.type === "err" ? "text-red-400" : "text-green-400"
                  }
                >
                  {entry.line}
                </div>
              ))
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
