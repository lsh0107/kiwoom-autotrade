import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TradingLogs } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 트레이딩 프로세스 로그 조회 훅 (10초 폴링) */
export function useTradingLogs(enabled = true) {
  return useQuery({
    queryKey: QUERY_KEYS.TRADING_LOGS,
    queryFn: () =>
      api.get<TradingLogs>(`${API_PATHS.BOT_TRADING_LOGS}?lines=50`, {
        skipCache: true,
      }),
    enabled,
    refetchInterval: enabled ? 10_000 : false,
    staleTime: 8_000,
    retry: 1,
  });
}
