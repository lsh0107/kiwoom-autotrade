import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TradeHistoryItem } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 당일 매매 이력 조회 훅 */
export function useTradeHistory() {
  return useQuery({
    queryKey: QUERY_KEYS.TRADE_HISTORY,
    queryFn: () =>
      api.get<TradeHistoryItem[]>(
        `${API_PATHS.BOT_TRADE_HISTORY}?limit=50`,
      ),
    staleTime: 30_000,
    retry: 1,
  });
}
