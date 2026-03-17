import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OHLCVData } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 일봉 차트 데이터 조회 훅 */
export function useDailyChart(symbol: string) {
  return useQuery({
    queryKey: QUERY_KEYS.DAILY_CHART(symbol),
    queryFn: () =>
      api.get<OHLCVData[]>(`${API_PATHS.DAILY_CHART(symbol)}?days=60`),
    enabled: !!symbol,
    staleTime: 60_000,
    retry: 1,
  });
}
