import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { BrokerCredential } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 브로커 자격증명 목록 조회 훅 */
export function useCredentials() {
  return useQuery({
    queryKey: QUERY_KEYS.CREDENTIALS,
    queryFn: () =>
      api.get<BrokerCredential[]>(API_PATHS.CREDENTIALS, { skipCache: true }),
    staleTime: 60_000,
    retry: 1,
  });
}
