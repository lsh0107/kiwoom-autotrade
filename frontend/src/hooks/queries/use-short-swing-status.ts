import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ShortSwingStatus } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** Short Swing 전략 상태 조회 훅 */
export function useShortSwingStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.SHORT_SWING_STATUS,
    queryFn: () => api.get<ShortSwingStatus>(API_PATHS.SHORT_SWING_STATUS),
    staleTime: 30_000,
  });
}
