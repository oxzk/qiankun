import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  /**
   * 将样式与属性转交给子元素。
   */
  asChild?: boolean;
}

/**
 * 通用多行输入框组件。
 */
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, asChild = false, children, ...props }, ref) => {
  const classNames = cn(
    "flex min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:border-muted disabled:bg-muted/70 disabled:text-muted-foreground disabled:shadow-none disabled:opacity-100",
    className,
  );

  if (asChild) {
    return (
      <Slot className={classNames} ref={ref} {...props}>
        {children}
      </Slot>
    );
  }

  return (
    <Slot className={classNames} ref={ref} {...props}>
      <textarea />
    </Slot>
  );
});
Textarea.displayName = "Textarea";

export { Textarea };
