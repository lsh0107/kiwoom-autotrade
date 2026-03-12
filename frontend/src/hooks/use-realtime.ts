"use client";

import { useEffect, useRef, useState, useCallback } from "react";

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
    if (symbols.length === 0) return;
    if (typeof window === "undefined") return;

    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;

      const ws = new WebSocket(
        `ws://${window.location.host}/api/v1/ws/market`,
      );
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setIsReconnecting(false);
        retryCountRef.current = 0;
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
  }, [symbols, clearReconnectTimer]);

  return { ticks, isConnected, isReconnecting };
}
