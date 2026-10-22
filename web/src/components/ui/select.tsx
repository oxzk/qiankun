import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const EMPTY_VALUE = "__scalor_empty__";

interface SelectOption {
  value: string;
  label: React.ReactNode;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  options: SelectOption[];
  onValueChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
}

/**
 * Radix 下拉选择框。
 */
export function Select({ value, options, onValueChange, placeholder, disabled, required, className }: SelectProps): JSX.Element {
  return (
    <SelectPrimitive.Root value={toRadixValue(value)} onValueChange={(nextValue) => onValueChange(fromRadixValue(nextValue))} disabled={disabled} required={required}>
      <SelectPrimitive.Trigger
        className={cn(
          "flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:border-muted disabled:bg-muted/70 disabled:text-muted-foreground disabled:shadow-none disabled:opacity-100",
          className,
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon asChild>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content className="z-50 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md">
          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={toRadixValue(option.value)}
                disabled={option.disabled}
                className="relative flex h-8 cursor-default select-none items-center rounded-sm py-1 pl-8 pr-2 text-sm outline-none focus:bg-muted focus:text-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              >
                <SelectPrimitive.ItemIndicator className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                  <Check className="h-4 w-4" />
                </SelectPrimitive.ItemIndicator>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

/**
 * 将业务空值映射为 Radix 可接受的选项值。
 */
function toRadixValue(value: string): string {
  return value === "" ? EMPTY_VALUE : value;
}

/**
 * 将 Radix 内部空值映射回业务空值。
 */
function fromRadixValue(value: string): string {
  return value === EMPTY_VALUE ? "" : value;
}
