import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StockSearchResult } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

/** 종목 검색 훅 — 한글/코드 모두 지원. q가 빈 문자열이면 비활성화 */
export function useSearchStocks(
  q: string,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: QUERY_KEYS.SEARCH_STOCKS(q),
    queryFn: () =>
      api.get<StockSearchResult[]>(
        `${API_PATHS.SEARCH_STOCKS}?q=${encodeURIComponent(q)}&limit=10`,
      ),
    enabled: (options?.enabled ?? true) && q.length > 0,
    staleTime: 30_000,
    retry: false,
  });
}
