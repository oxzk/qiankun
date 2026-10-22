import * as LabelPrimitive from "@radix-ui/react-label";
import { Children, isValidElement, useState, type ReactNode, type SyntheticEvent } from "react";

export interface FieldProps {
  /**
   * 字段标签。
   */
  label: string;
  /**
   * 字段内容。
   */
  children: ReactNode;
  /**
   * 是否必填。
   */
  required?: boolean;
  /**
   * 是否使用行内布局。
   */
  inline?: boolean;
  /**
   * 外部错误状态。
   */
  error?: boolean;
  /**
   * 外部错误提示。
   */
  errorMessage?: string;
}

/**
 * 标准字段标签。
 */
export function Field({ label, children, required, inline, error, errorMessage }: FieldProps): JSX.Element {
  const [showError, setShowError] = useState(false);
  const isRequired = required ?? hasRequiredChild(children);
  const shouldShowError = Boolean(error) || (isRequired && showError);
  const resolvedErrorMessage = errorMessage || (isRequired ? `${label}不能为空` : "输入无效");

  /**
   * 提交时捕获必填校验失败并显示自定义提示。
   */
  function handleInvalid(event: SyntheticEvent<HTMLElement>): void {
    if (!isRequired) return;
    if (!isEmptyRequiredControl(event.target)) return;
    event.preventDefault();
    setShowError(true);
  }

  /**
   * 输入有效值后清理当前字段提示。
   */
  function handleInput(event: SyntheticEvent<HTMLElement>): void {
    if (!showError) return;
    if (isEmptyRequiredControl(event.target)) return;
    setShowError(false);
  }

  return (
    <LabelPrimitive.Root
      className={inline ? "relative grid gap-1.5" : "relative grid gap-1.5"}
      onInvalidCapture={handleInvalid}
      onInputCapture={handleInput}
      onChangeCapture={handleInput}
    >
      <span className={inline ? "grid grid-cols-[6rem_minmax(0,1fr)] items-center gap-2" : "grid gap-1.5"}>
        <span className="field-label whitespace-nowrap">
          {label}
          {isRequired ? <span className="ml-1 text-destructive">*</span> : null}
        </span>
        {children}
      </span>
      {shouldShowError ? (
        inline ? (
          <span className="absolute left-[calc(6rem+0.5rem)] top-[calc(100%+0.25rem)] text-xs leading-4 text-destructive">
            {resolvedErrorMessage}
          </span>
        ) : (
          <span className="absolute left-0 top-[calc(100%+0.25rem)] text-xs leading-4 text-destructive">
            {resolvedErrorMessage}
          </span>
        )
      ) : null}
    </LabelPrimitive.Root>
  );
}

/**
 * 判断字段内容是否包含必填表单控件。
 */
function hasRequiredChild(children: ReactNode): boolean {
  return Children.toArray(children).some((child) => {
    if (!isValidElement<{ required?: boolean; children?: ReactNode }>(child)) return false;
    return Boolean(child.props.required) || hasRequiredChild(child.props.children);
  });
}

/**
 * 判断必填控件是否为空。
 */
function isEmptyRequiredControl(target: EventTarget): boolean {
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) {
    return target.required && target.validity.valueMissing;
  }
  return false;
}
