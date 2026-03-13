import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StrategyConfigSuggestion } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 전략 파라미터 제안 목록 조회 훅 (pending 상태만) */
export function useConfigSuggestions() {
  return useQuery({
    queryKey: QUERY_KEYS.STRATEGY_SUGGESTIONS,
    queryFn: () =>
      api.get<StrategyConfigSuggestion[]>(API_PATHS.STRATEGY_SUGGESTIONS, {
        skipCache: true,
      }),
    staleTime: 30_000,
    retry: 1,
  });
}
