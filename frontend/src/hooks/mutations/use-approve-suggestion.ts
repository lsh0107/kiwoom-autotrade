import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

interface SuggestionActionParams {
  id: string;
  action: "approve" | "reject";
}

/** 전략 파라미터 제안 승인/거부 뮤테이션 훅 */
export function useApproveSuggestion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, action }: SuggestionActionParams) => {
      const path =
        action === "approve"
          ? API_PATHS.STRATEGY_SUGGESTION_APPROVE(id)
          : API_PATHS.STRATEGY_SUGGESTION_REJECT(id);
      return api.post(path, { reviewed_by: "user" });
    },
    onSuccess: (_, { action }) => {
      const label = action === "approve" ? "승인" : "거부";
      toast.success(`제안이 ${label}되었습니다.`);
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.STRATEGY_SUGGESTIONS,
      });
      // 승인 시 전략 설정도 갱신
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.STRATEGY_CONFIG });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "처리에 실패했습니다.";
      toast.error(msg);
    },
  });
}
