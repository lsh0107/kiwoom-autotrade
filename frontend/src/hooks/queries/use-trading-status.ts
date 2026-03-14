import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TradingStatus } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 트레이딩 프로세스 상태 조회 훅 (5초 폴링) */
export function useTradingStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.TRADING_STATUS,
    queryFn: () =>
      api.get<TradingStatus>(API_PATHS.BOT_TRADING_STATUS, {
        skipCache: true,
      }),
    refetchInterval: 5_000,
    staleTime: 4_000,
    retry: 1,
  });
}
