import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Primitive } from "@radix-ui/react-primitive";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;

/**
 * 弹窗遮罩层。
 */
const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay ref={ref} className={cn("fixed inset-0 z-50 bg-black/40 backdrop-blur-sm", className)} {...props} />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

/**
 * 弹窗内容容器。
 */
export const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, onOpenAutoFocus, onPointerDownOutside, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      onOpenAutoFocus={(event) => {
        event.preventDefault();
        onOpenAutoFocus?.(event);
      }}
      onPointerDownOutside={(event) => {
        // Prevent closing the dialog on backdrop clicks to avoid losing form state
        // and to prevent select dropdown portals from closing the modal.
        event.preventDefault();
        onPointerDownOutside?.(event);
      }}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 grid max-h-[88vh] w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 gap-4 overflow-x-hidden overflow-y-auto rounded-lg border bg-popover p-6 text-popover-foreground shadow-apple",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-md opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0">
        <X className="h-4 w-4" />
        <Primitive.span className="sr-only">关闭</Primitive.span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

/**
 * 弹窗头部。
 */
export function DialogHeader({ className, ...props }: React.ComponentPropsWithoutRef<typeof Primitive.div>): JSX.Element {
  return <Primitive.div className={cn("flex flex-col gap-1.5 text-left", className)} {...props} />;
}

export const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("text-lg font-semibold leading-none tracking-normal", className)} {...props} />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;
