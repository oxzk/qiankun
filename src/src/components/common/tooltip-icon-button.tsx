import type { ReactNode } from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export interface TooltipIconButtonProps extends Omit<ButtonProps, "children" | "size" | "aria-label"> {
  /**
   * 按钮提示文本。
   */
  label: string;
  /**
   * 按钮图标。
   */
  children: ReactNode;
}

/**
 * 带 Tooltip 的图标按钮。
 */
export function TooltipIconButton({ label, children, ...props }: TooltipIconButtonProps): JSX.Element {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button size="icon" aria-label={label} {...props}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
