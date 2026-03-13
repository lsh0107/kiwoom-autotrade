import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { KillSwitchResponse } from "@/types/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** 거래 재개 뮤테이션 훅 — Soft/Hard Stop 해제 */
export function useResumeTrading() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.post<KillSwitchResponse>(API_PATHS.TRADING_RESUME),
    onSuccess: () => {
      toast.success("거래가 재개되었습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.KILL_SWITCH_STATUS });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "거래 재개 실패";
      toast.error(msg);
    },
  });
}
