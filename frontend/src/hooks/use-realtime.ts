"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface TickData {
  symbol: string;
  price: number;
  volume: number;
  timestamp: string;
  change?: number;
  changePct?: number;
}

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;
const RECONNECT_MAX_RETRIES = 5;

/** WebSocket 실시간 시세 훅 — symbols 변경 시 재연결, 0개면 연결 안 함 */
export function useRealtime(symbols: string[]) {
  // 중복 제거 + 정렬 → 문자열 키로 안정화 (참조 비교 방지)
  const uniqueSymbols = useMemo(
    () => [...new Set(symbols)].sort(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [symbols.slice().sort().join(",")],
  );
  const symbolsKey = uniqueSymbols.join(",");

  const [ticks, setTicks] = useState<Map<string, TickData>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** 언마운트 여부 추적 — 정리 후 재연결 방지 */
  const unmountedRef = useRef(false);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (uniqueSymbols.length === 0) return;
    if (typeof window === "undefined") return;

    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(
        `${protocol}//${window.location.host}/api/v1/ws/market`,
      );
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setIsReconnecting(false);
        retryCountRef.current = 0;
        ws.send(JSON.stringify({ action: "subscribe", symbols: uniqueSymbols, type: "0B" }));
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

      ws.onclose = () => {
        setIsConnected(false);
        scheduleReconnect();
      };

      ws.onerror = () => {
        setIsConnected(false);
        ws.close();
      };
    }

    function scheduleReconnect() {
      if (unmountedRef.current) return;
      if (retryCountRef.current >= RECONNECT_MAX_RETRIES) {
        setIsReconnecting(false);
        return;
      }

      setIsReconnecting(true);
      const delay = Math.min(
        RECONNECT_BASE_MS * 2 ** retryCountRef.current,
        RECONNECT_MAX_MS,
      );
      retryCountRef.current += 1;

      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    }

    connect();

    return () => {
      unmountedRef.current = true;
      clearReconnectTimer();
      wsRef.current?.close();
    };
    // symbolsKey: 문자열 비교로 배열 참조 변경에 의한 불필요한 재연결 방지
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey, clearReconnectTimer]);

  return { ticks, isConnected, isReconnecting };
}
