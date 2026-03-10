import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Strategy } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 자동매매 전략 목록 조회 훅 */
export function useStrategies() {
  return useQuery({
    queryKey: QUERY_KEYS.STRATEGIES,
    queryFn: () =>
      api.get<Strategy[]>(API_PATHS.STRATEGIES, { skipCache: true }),
    staleTime: 30_000,
    retry: 1,
  });
}
