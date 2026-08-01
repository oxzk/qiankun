import {
  useMutation,
  useQueryClient,
  type QueryKey,
  type UseMutationResult,
} from "@tanstack/react-query";
import { getErrorMessage } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import type { ToastMessage } from "@/components/ui/sonner";

export interface ToastMutationOptions<TData, TVariables> {
  /**
   * 实际提交函数。
   */
  mutationFn: (variables: TVariables) => Promise<TData>;
  /**
   * 成功提示标题。
   */
  successTitle?: string | ((data: TData, variables: TVariables) => string | undefined);
  /**
   * 成功提示完整内容。
   */
  successToast?: (data: TData, variables: TVariables) => Omit<ToastMessage, "id"> | undefined;
  /**
   * 失败提示标题。
   */
  errorTitle: string;
  /**
   * 成功后需要失效的缓存键。
   */
  invalidate?: readonly QueryKey[];
  /**
   * 成功后的业务回调。
   */
  onSuccess?: (data: TData, variables: TVariables) => void;
  /**
   * 失败后的业务回调。
   */
  onError?: (error: unknown, variables: TVariables) => void;
}

/**
 * 创建带统一 toast 和缓存失效行为的 mutation。
 */
export function useToastMutation<TData, TVariables>({
  mutationFn,
  successTitle,
  successToast,
  errorTitle,
  invalidate = [],
  onSuccess,
  onError,
}: ToastMutationOptions<TData, TVariables>): UseMutationResult<TData, unknown, TVariables> {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn,
    onSuccess: (data, variables) => {
      const message = successToast?.(data, variables);
      const title = typeof successTitle === "function" ? successTitle(data, variables) : successTitle;
      if (message) {
        toast(message);
      } else if (title) {
        toast({ title });
      }
      invalidate.forEach((queryKey) => {
        void queryClient.invalidateQueries({ queryKey });
      });
      onSuccess?.(data, variables);
    },
    onError: (error, variables) => {
      toast({ title: errorTitle, description: getErrorMessage(error), variant: "destructive" });
      onError?.(error, variables);
    },
  });
}
