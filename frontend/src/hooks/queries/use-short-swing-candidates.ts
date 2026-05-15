import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ShortSwingCandidatesResponse } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** Short Swing 후보 종목 조회 훅 */
export function useShortSwingCandidates(date: string) {
  return useQuery({
    queryKey: QUERY_KEYS.SHORT_SWING_CANDIDATES(date),
    queryFn: () =>
      api.get<ShortSwingCandidatesResponse>(
        `${API_PATHS.SHORT_SWING_CANDIDATES}?date=${date}&limit=20`,
      ),
    staleTime: 60_000,
    enabled: date.length > 0,
  });
}
