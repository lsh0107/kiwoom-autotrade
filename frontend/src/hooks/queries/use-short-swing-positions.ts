import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ShortSwingPositionsResponse } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** Short Swing 포지션 조회 훅 */
export function useShortSwingPositions(status: string = "open") {
  return useQuery({
    queryKey: QUERY_KEYS.SHORT_SWING_POSITIONS(status),
    queryFn: () =>
      api.get<ShortSwingPositionsResponse>(
        `${API_PATHS.SHORT_SWING_POSITIONS}?status=${status}&limit=50`,
      ),
    staleTime: 30_000,
  });
}
