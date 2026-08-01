import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Toaster, type ToastMessage } from "@/components/ui/sonner";

interface ToastContextValue {
  toast: (message: Omit<ToastMessage, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/**
 * 提供全局 Toast 能力。
 */
export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  const dismiss = useCallback((id: string) => {
    setMessages((current) => current.filter((message) => message.id !== id));
  }, []);

  const toast = useCallback((message: Omit<ToastMessage, "id">) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setMessages((current) => [...current, { ...message, id }]);
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Toaster messages={messages} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

/**
 * 读取 Toast 调用函数。
 */
export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast 必须在 ToastProvider 内使用");
  return context;
}
