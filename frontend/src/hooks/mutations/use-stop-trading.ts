import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import type { TradingActionResponse } from "@/types/api";
import { toast } from "sonner";

/** 트레이딩 프로세스 중지 뮤테이션 훅 */
export function useStopTrading() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      api.post<TradingActionResponse>(API_PATHS.BOT_TRADING_STOP),
    onSuccess: () => {
      toast.success("자동매매 프로세스를 중지했습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.TRADING_STATUS });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "중지에 실패했습니다.";
      toast.error(msg);
    },
  });
}
