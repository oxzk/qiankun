import * as React from "react";
import { Primitive } from "@radix-ui/react-primitive";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors", {
  variants: {
    variant: {
      default: "border-transparent bg-primary text-primary-foreground",
      secondary: "border-transparent bg-secondary text-secondary-foreground",
      outline: "text-foreground",
      destructive: "border-transparent bg-destructive text-destructive-foreground",
    },
  },
  defaultVariants: {
    variant: "secondary",
  },
});

export interface BadgeProps extends React.ComponentPropsWithoutRef<typeof Primitive.span>, VariantProps<typeof badgeVariants> {}

/**
 * 状态徽标组件。
 */
export function Badge({ className, variant, ...props }: BadgeProps): JSX.Element {
  return <Primitive.span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
