import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

export interface CheckboxOption {
  value: string | number;
  label: string;
  description?: string;
}

interface CheckboxGroupProps {
  options: CheckboxOption[];
  value: (string | number)[];
  onChange: (value: (string | number)[]) => void;
  className?: string;
  orientation?: "horizontal" | "vertical";
}

export function CheckboxGroup({ options, value, onChange, className, orientation = "vertical" }: CheckboxGroupProps): JSX.Element {
  function toggleOption(optionValue: string | number): void {
    if (value.includes(optionValue)) {
      onChange(value.filter((v) => v !== optionValue));
    } else {
      onChange([...value, optionValue]);
    }
  }

  if (options.length === 0) {
    return <div className="text-sm text-muted-foreground">暂无选项</div>;
  }

  return (
    <div className={cn(
      "flex gap-4",
      orientation === "vertical" ? "flex-col" : "flex-row flex-wrap items-center",
      className
    )}>
      {options.map((option) => (
        <div key={option.value} className="flex items-center space-x-2">
          <Checkbox
            id={`checkbox-${option.value}`}
            checked={value.includes(option.value)}
            onCheckedChange={() => toggleOption(option.value)}
          />
          <label
            htmlFor={`checkbox-${option.value}`}
            className={cn(
              "cursor-pointer text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
              option.description && "grid gap-0.5"
            )}
          >
            {option.label}
            {option.description ? (
              <span className="text-xs font-normal text-muted-foreground">{option.description}</span>
            ) : null}
          </label>
        </div>
      ))}
    </div>
  );
}
