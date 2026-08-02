import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Primitive } from "@radix-ui/react-primitive";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogPortal = DialogPrimitive.Portal;
export const DialogClose = DialogPrimitive.Close;

/**
 * 弹窗遮罩层。
 */
export const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

/**
 * 弹窗内容容器。
 * 顶部固定，内部内容区域支持独立滚动，避免弹窗整体溢出屏幕。
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
        // 防止点击背景误关导致表单状态丢失
        event.preventDefault();
        onPointerDownOutside?.(event);
      }}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-apple animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 z-10 rounded-md p-1 opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-0">
        <X className="h-4 w-4" />
        <Primitive.span className="sr-only">关闭</Primitive.span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

/**
 * 弹窗固定头部。
 */
export function DialogHeader({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof Primitive.div>): JSX.Element {
  return (
    <Primitive.div
      className={cn(
        "flex shrink-0 flex-col gap-1.5 border-b border-border/50 px-6 py-4 text-left pr-12 bg-background/60 backdrop-blur-xs",
        className,
      )}
      {...props}
    />
  );
}

export const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-base font-semibold leading-none tracking-normal text-foreground", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

export const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-xs text-muted-foreground leading-relaxed", className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

/**
 * 弹窗可滚动内容主体。
 */
export function DialogBody({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof Primitive.div>): JSX.Element {
  return (
    <Primitive.div
      className={cn("min-h-0 flex-1 overflow-y-auto px-6 py-4 space-y-4", className)}
      {...props}
    />
  );
}

/**
 * 弹窗底部操作区。
 */
export function DialogFooter({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof Primitive.div>): JSX.Element {
  return (
    <Primitive.div
      className={cn(
        "flex shrink-0 items-center justify-end gap-2 border-t border-border/50 px-6 py-3.5 bg-muted/20",
        className,
      )}
      {...props}
    />
  );
}
