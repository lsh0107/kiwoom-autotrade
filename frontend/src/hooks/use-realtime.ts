"use client";

import { useEffect, useRef, useState } from "react";

export interface TickData {
  symbol: string;
  price: number;
  volume: number;
  timestamp: string;
  change?: number;
  changePct?: number;
}

/** WebSocket 실시간 시세 훅 — symbols 변경 시 재연결, 0개면 연결 안 함 */
export function useRealtime(symbols: string[]) {
  const [ticks, setTicks] = useState<Map<string, TickData>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (symbols.length === 0) return;
    if (typeof window === "undefined") return;

    const ws = new WebSocket(
      `ws://${window.location.host}/api/v1/ws/market`,
    );
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({ action: "subscribe", symbols, type: "0B" }));
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as TickData & {
          type: string;
        };
        if (data.type === "tick") {
          setTicks((prev) => {
            const next = new Map(prev);
            next.set(data.symbol, data);
            return next;
          });
        }
      } catch {
        // JSON 파싱 실패 무시
      }
    };

    ws.onclose = () => setIsConnected(false);
    ws.onerror = () => setIsConnected(false);

    return () => {
      ws.close();
    };
  }, [symbols]); // 심볼 목록 변경 시 재연결

  return { ticks, isConnected };
}
