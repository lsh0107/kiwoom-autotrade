import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { LLMDecision } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** LLM 결정 목록 조회 훅 */
export function useDecisions(statusFilter?: string) {
  const params = statusFilter ? `?status=${statusFilter}` : "";
  return useQuery({
    queryKey: [...QUERY_KEYS.DECISIONS, statusFilter ?? "all"],
    queryFn: () => api.get<LLMDecision[]>(`${API_PATHS.DECISIONS}${params}`),
    staleTime: 30_000,
    retry: 1,
  });
}
