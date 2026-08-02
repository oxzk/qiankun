import { useCallback, useRef, useState, type ReactNode } from "react";
import { ConfirmDialog, type ConfirmDialogProps } from "@/components/common/confirm-dialog";

export interface ConfirmOptions {
  title: string;
  description: string;
  confirmText?: string;
  confirmVariant?: ConfirmDialogProps["confirmVariant"];
  confirmDisabled?: boolean;
  children?: ReactNode;
}

export interface UseConfirmResult {
  /**
   * 触发二次确认弹窗，返回用户是否点击了确认。
   */
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  /**
   * 确认弹窗组件，需挂载在调用者组件中。
   */
  ConfirmDialogComponent: () => JSX.Element | null;
}

/**
 * 声明式/Promise 式二次确认 Hook。
 */
export function useConfirm(): UseConfirmResult {
  const [state, setState] = useState<(ConfirmOptions & { open: boolean }) | null>(null);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const handleClose = useCallback(() => {
    setState((current) => (current ? { ...current, open: false } : null));
    if (resolverRef.current) {
      resolverRef.current(false);
      resolverRef.current = null;
    }
  }, []);

  const handleConfirm = useCallback(() => {
    setState((current) => (current ? { ...current, open: false } : null));
    if (resolverRef.current) {
      resolverRef.current(true);
      resolverRef.current = null;
    }
  }, []);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
      setState({
        ...options,
        open: true,
      });
    });
  }, []);

  const ConfirmDialogComponent = useCallback((): JSX.Element | null => {
    if (!state) return null;
    return (
      <ConfirmDialog
        open={state.open}
        title={state.title}
        description={state.description}
        confirmText={state.confirmText}
        confirmVariant={state.confirmVariant}
        confirmDisabled={state.confirmDisabled}
        onOpenChange={(open) => {
          if (!open) handleClose();
        }}
        onConfirm={handleConfirm}
      >
        {state.children}
      </ConfirmDialog>
    );
  }, [handleClose, handleConfirm, state]);

  return { confirm, ConfirmDialogComponent };
}
