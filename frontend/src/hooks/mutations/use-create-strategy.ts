import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import type { Strategy } from "@/types/api";
import { toast } from "sonner";

export interface CreateStrategyRequest {
  name: string;
  description?: string;
  symbols: string[];
  max_investment: number;
  max_loss_pct: number;
  max_position_pct: number;
}

/** 전략 생성 뮤테이션 훅 */
export function useCreateStrategy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateStrategyRequest) =>
      api.post<Strategy>(API_PATHS.STRATEGIES, data),
    onSuccess: () => {
      toast.success("전략이 생성되었습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.STRATEGIES });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "전략 생성에 실패했습니다.";
      toast.error(msg);
    },
  });
}
