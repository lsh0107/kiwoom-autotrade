import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { KillSwitchResponse } from "@/types/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** Hard Stop 뮤테이션 훅 — 모든 포지션 즉시 청산 */
export function useHardStop() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      api.post<KillSwitchResponse>(API_PATHS.TRADING_HARD_STOP, {
        confirm: true,
      }),
    onSuccess: () => {
      toast.success("Hard Stop 발동 — 모든 포지션이 청산됩니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.KILL_SWITCH_STATUS });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "Hard Stop 실패";
      toast.error(msg);
    },
  });
}
