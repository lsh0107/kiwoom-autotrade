import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Orderbook } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 종목 호가창 조회 훅 (symbol이 있을 때만 활성화) */
export function useOrderbook(symbol: string) {
  return useQuery({
    queryKey: QUERY_KEYS.ORDERBOOK(symbol),
    queryFn: () =>
      api.get<Orderbook>(API_PATHS.ORDERBOOK(symbol), { skipCache: true }),
    enabled: symbol.length > 0,
    staleTime: 10_000,
    retry: 1,
  });
}
