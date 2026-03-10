import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** 전략 시작/중지 뮤테이션 훅 */
export function useToggleStrategy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => {
      const action = status === "active" ? "stop" : "start";
      return api.post(API_PATHS.STRATEGY_ACTION(id, action));
    },
    onSuccess: (_, variables) => {
      toast.success(
        variables.status === "active"
          ? "전략이 중지되었습니다."
          : "전략이 시작되었습니다.",
      );
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.STRATEGIES });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "실패했습니다.";
      toast.error(msg);
    },
  });
}
