import * as ToastPrimitive from "@radix-ui/react-toast";
import { Primitive } from "@radix-ui/react-primitive";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  variant?: "default" | "destructive";
}

export interface ToasterProps {
  messages: ToastMessage[];
  onDismiss: (id: string) => void;
}

/**
 * Toast 消息容器。
 */
export function Toaster({ messages, onDismiss }: ToasterProps): JSX.Element {
  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {messages.map((message) => (
        <ToastPrimitive.Root
          key={message.id}
          open
          duration={4200}
          onOpenChange={(open) => {
            if (!open) onDismiss(message.id);
          }}
          className="glass-card fixed right-4 top-4 z-[100] grid w-[calc(100vw-2rem)] max-w-sm gap-1 rounded-lg p-4 shadow-apple data-[state=closed]:animate-out"
        >
          <Primitive.div className="flex items-start justify-between gap-3">
            <Primitive.div>
              <ToastPrimitive.Title className={message.variant === "destructive" ? "text-sm font-semibold text-destructive" : "text-sm font-semibold"}>
                {message.title}
              </ToastPrimitive.Title>
              {message.description ? (
                <ToastPrimitive.Description className="mt-1 text-sm text-muted-foreground">{message.description}</ToastPrimitive.Description>
              ) : null}
            </Primitive.div>
            <Tooltip>
              <TooltipTrigger asChild>
                <ToastPrimitive.Close asChild>
                  <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="关闭">
                    <X className="h-4 w-4" />
                  </Button>
                </ToastPrimitive.Close>
              </TooltipTrigger>
              <TooltipContent>关闭</TooltipContent>
            </Tooltip>
          </Primitive.div>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport className="fixed right-4 top-4 z-[100] flex max-h-screen w-[calc(100vw-2rem)] max-w-sm flex-col gap-2 outline-none" />
    </ToastPrimitive.Provider>
  );
}
