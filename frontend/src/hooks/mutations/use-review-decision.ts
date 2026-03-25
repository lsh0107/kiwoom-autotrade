import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

interface ReviewDecisionParams {
  id: string;
  action: "approve" | "reject";
}

/** LLM 결정 승인/거부 뮤테이션 훅 */
export function useReviewDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, action }: ReviewDecisionParams) => {
      const path =
        action === "approve"
          ? API_PATHS.DECISION_APPROVE(id)
          : API_PATHS.DECISION_REJECT(id);
      return api.post(path);
    },
    onSuccess: (_, { action }) => {
      const label = action === "approve" ? "승인" : "거부";
      toast.success(`결정이 ${label}되었습니다.`);
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.DECISIONS });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "처리에 실패했습니다.";
      toast.error(msg);
    },
  });
}
