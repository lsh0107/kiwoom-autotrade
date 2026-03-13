import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { StrategyConfigUpdateRequest } from "@/types/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** 전략 파라미터 업데이트 뮤테이션 훅 */
export function useUpdateStrategyConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: StrategyConfigUpdateRequest) =>
      api.put(API_PATHS.STRATEGY_CONFIG, data),
    onSuccess: () => {
      toast.success("전략 파라미터가 저장되었습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.STRATEGY_CONFIG });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "저장에 실패했습니다.";
      toast.error(msg);
    },
  });
}
