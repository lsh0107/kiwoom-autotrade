import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Quote } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 종목 현재가 조회 훅 (symbol이 있을 때만 활성화) */
export function useQuote(symbol: string) {
  return useQuery({
    queryKey: QUERY_KEYS.QUOTE(symbol),
    queryFn: () =>
      api.get<Quote>(API_PATHS.QUOTE(symbol), { skipCache: true }),
    enabled: symbol.length > 0,
    staleTime: 10_000,
    retry: 1,
  });
}
