import * as React from "react";
import { Primitive } from "@radix-ui/react-primitive";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps extends React.ComponentPropsWithoutRef<typeof Primitive.button>, VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

/**
 * 通用按钮组件。
 */
const Button = React.forwardRef<React.ElementRef<typeof Primitive.button>, ButtonProps>(({ className, variant, size, loading = false, disabled, children, ...props }, ref) => {
  return (
    <Primitive.button className={cn(buttonVariants({ variant, size, className }))} ref={ref} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {children}
    </Primitive.button>
  );
});
Button.displayName = "Button";

export { Button };
