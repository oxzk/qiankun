import * as React from "react";
import { Primitive } from "@radix-ui/react-primitive";
import { cn } from "@/lib/utils";

/**
 * 通用输入框组件。
 */
const Input = React.forwardRef<React.ElementRef<typeof Primitive.input>, React.ComponentPropsWithoutRef<typeof Primitive.input>>(({ className, type, ...props }, ref) => (
  <Primitive.input
    type={type}
    className={cn(
      "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:border-muted disabled:bg-muted/70 disabled:text-muted-foreground disabled:shadow-none disabled:opacity-100",
      className,
    )}
    ref={ref}
    {...props}
  />
));
Input.displayName = "Input";

export { Input };
