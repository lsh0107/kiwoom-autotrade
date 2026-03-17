import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StrategyConfigItem } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 전략 파라미터 목록 조회 훅 */
export function useStrategyConfig() {
  return useQuery({
    queryKey: QUERY_KEYS.STRATEGY_CONFIG,
    queryFn: () =>
      api.get<StrategyConfigItem[]>(API_PATHS.STRATEGY_CONFIG),
    staleTime: 30_000,
    retry: 1,
  });
}
