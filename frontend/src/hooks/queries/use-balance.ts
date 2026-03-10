import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AccountBalance } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 계좌 잔고 조회 훅 */
export function useBalance() {
  return useQuery({
    queryKey: QUERY_KEYS.BALANCE,
    queryFn: () =>
      api.get<AccountBalance>(API_PATHS.BALANCE, { skipCache: true }),
    staleTime: 30_000,
    retry: 1,
  });
}
