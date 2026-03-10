import { useMutation } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { CreateOrderRequest } from "@/types/api";
import { API_PATHS } from "@/lib/constants";
import { getErrorMessage } from "@/lib/errors";
import { toast } from "sonner";

/** 주문 제출 뮤테이션 훅 */
export function usePlaceOrder() {
  return useMutation({
    mutationFn: (req: CreateOrderRequest) => api.post(API_PATHS.ORDERS, req),
    onSuccess: (_, variables) => {
      toast.success(
        `${variables.side === "BUY" ? "매수" : "매도"} 주문이 접수되었습니다.`,
      );
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError
          ? getErrorMessage(err.code, err.message)
          : "주문에 실패했습니다.";
      toast.error(msg);
    },
  });
}
