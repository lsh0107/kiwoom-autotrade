import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import type { StrategyRuntimeView } from "@/types/api";

/** 전략 런타임 토글 + budget 상태 조회 (design-025) */
export function useStrategyRuntime() {
  return useQuery({
    queryKey: QUERY_KEYS.STRATEGY_RUNTIME,
    queryFn: () => api.get<StrategyRuntimeView[]>(API_PATHS.STRATEGY_RUNTIME),
    staleTime: 10_000,
  });
}
