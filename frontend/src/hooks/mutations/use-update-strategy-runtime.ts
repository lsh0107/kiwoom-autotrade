import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import type { StrategyRuntimeView } from "@/types/api";
import { toast } from "sonner";

export interface StrategyRuntimePatchPayload {
  strategy: string;
  enabled?: boolean;
  budget_pct?: number;
  max_order_amount?: number;
  max_daily_orders?: number;
}

/** 전략 런타임 토글/budget 갱신 (design-025) */
export function useUpdateStrategyRuntime() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ strategy, ...patch }: StrategyRuntimePatchPayload) =>
      api.patch<StrategyRuntimeView>(
        API_PATHS.STRATEGY_RUNTIME_PATCH(strategy),
        patch,
      ),
    onSuccess: (_data, variables) => {
      toast.success(`${variables.strategy} 설정이 갱신되었습니다.`);
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.STRATEGY_RUNTIME });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.STRATEGY_CURRENT });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "갱신 실패했습니다.";
      toast.error(msg);
    },
  });
}
