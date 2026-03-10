import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import type { BrokerCredentialCreate } from "@/types/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** API 키 저장 뮤테이션 훅 */
export function useSaveCredential() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BrokerCredentialCreate) =>
      api.post(API_PATHS.CREDENTIALS, data),
    onSuccess: () => {
      toast.success("API 키가 저장되었습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CREDENTIALS });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "저장에 실패했습니다.";
      toast.error(msg);
    },
  });
}
