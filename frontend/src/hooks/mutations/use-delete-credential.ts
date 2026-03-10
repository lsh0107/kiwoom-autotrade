import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api";
import { API_PATHS, QUERY_KEYS } from "@/lib/constants";
import { toast } from "sonner";

/** API 키 삭제 뮤테이션 훅 */
export function useDeleteCredential() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(API_PATHS.CREDENTIAL(id)),
    onSuccess: () => {
      toast.success("자격증명이 삭제되었습니다.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CREDENTIALS });
    },
    onError: (err) => {
      const msg =
        err instanceof ApiClientError ? err.message : "삭제에 실패했습니다.";
      toast.error(msg);
    },
  });
}
