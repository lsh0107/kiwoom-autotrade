import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ResultFile, BacktestResult } from "@/types/api";
import { QUERY_KEYS, API_PATHS } from "@/lib/constants";

export interface ResultsData {
  fileList: ResultFile[];
  resultsMap: Map<string, BacktestResult>;
}

/** 백테스트 결과 파일 목록 및 상세 조회 훅 (최근 10건) */
export function useResults() {
  return useQuery({
    queryKey: QUERY_KEYS.RESULTS,
    queryFn: async (): Promise<ResultsData> => {
      const fileList = await api.get<ResultFile[]>(API_PATHS.RESULTS_LIST);

      const recent = fileList.slice(0, 10);
      const details = await Promise.all(
        recent.map(async (f) => {
          try {
            const data = await api.get<BacktestResult>(
              API_PATHS.RESULT(f.filename),
            );
            return [f.filename, data] as const;
          } catch {
            return null;
          }
        }),
      );

      const resultsMap = new Map<string, BacktestResult>();
      for (const entry of details) {
        if (entry) resultsMap.set(entry[0], entry[1]);
      }

      return { fileList, resultsMap };
    },
    staleTime: 60_000,
    retry: 1,
  });
}
