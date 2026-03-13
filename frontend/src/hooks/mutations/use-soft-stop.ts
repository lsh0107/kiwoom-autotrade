import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { KillSwitchResponse } from "@/types/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** Soft Stop 뮤테이션 훅 — 신규 주문 중단, 기존 포지션 유지 */
export function useSoftStop() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.post<KillSwitchResponse>(API_PATHS.TRADING_SOFT_STOP),
    onSuccess: () => {
      toast.success("Soft Stop 발동 — 신규 주문이 중단되었습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.KILL_SWITCH_STATUS });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "Soft Stop 실패";
      toast.error(msg);
    },
  });
}
