import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StrategyCurrentResponse } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 현재 활성 전략 현황 조회 훅 */
export function useStrategyCurrent() {
  return useQuery({
    queryKey: QUERY_KEYS.STRATEGY_CURRENT,
    queryFn: () =>
      api.get<StrategyCurrentResponse>(API_PATHS.STRATEGY_CURRENT),
    staleTime: 30_000,
  });
}
