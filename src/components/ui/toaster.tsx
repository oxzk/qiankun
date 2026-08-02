import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastIcon,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";
import { useToast } from "@/hooks/use-toast";

/**
 * 全局 Toaster 消息渲染容器。
 */
export function Toaster(): JSX.Element {
  const { toasts, dismiss } = useToast();

  return (
    <ToastProvider swipeDirection="right" duration={4500}>
      {toasts.map(function ({ id, title, description, action, variant, ...props }) {
        return (
          <Toast key={id} variant={variant} onOpenChange={(open) => !open && dismiss(id)} {...props}>
            <div className="flex items-start gap-3">
              <ToastIcon variant={variant} />
              <div className="grid gap-0.5">
                {title ? <ToastTitle>{title}</ToastTitle> : null}
                {description ? <ToastDescription>{description}</ToastDescription> : null}
              </div>
            </div>
            {action}
            <ToastClose />
          </Toast>
        );
      })}
      <ToastViewport />
    </ToastProvider>
  );
}
