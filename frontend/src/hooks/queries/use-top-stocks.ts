import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TopStockItem } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 오늘의 추천 종목 훅 — 모멘텀 스크리닝 상위 종목 */
export function useTopStocks(profile = "momentum_daily", limit = 10) {
  return useQuery({
    queryKey: QUERY_KEYS.TOP_STOCKS(profile),
    queryFn: () =>
      api.get<TopStockItem[]>(
        `${API_PATHS.TOP_STOCKS}?profile=${profile}&limit=${limit}`,
      ),
    staleTime: 60_000,
    retry: false,
  });
}
