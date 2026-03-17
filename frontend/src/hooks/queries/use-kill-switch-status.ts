import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { KillSwitchStatus } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** Kill Switch 현재 상태 조회 훅 */
export function useKillSwitchStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.KILL_SWITCH_STATUS,
    queryFn: () =>
      api.get<KillSwitchStatus>(API_PATHS.KILL_SWITCH_STATUS),
    staleTime: 10_000,
    retry: 1,
  });
}
