import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** Kill Switch 뮤테이션 훅 — 모든 전략 긴급 중지 */
export function useKillSwitch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.post(API_PATHS.KILL_SWITCH, { active: true }),
    onSuccess: () => {
      toast.success("Kill Switch 발동 — 모든 전략이 중지되었습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.STRATEGIES });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "Kill Switch 실패";
      toast.error(msg);
    },
  });
}
