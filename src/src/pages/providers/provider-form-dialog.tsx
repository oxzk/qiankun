import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm, type Resolver } from "react-hook-form";
import { CodeEditor, Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { providerFormSchema, toProviderPayload, type ProviderFormValues } from "@/lib/forms";
import type { ProviderInfo, ProviderPayload } from "@/types";

export interface ProviderFormDialogProps {
  /**
   * 是否打开弹窗。
   */
  open: boolean;
  /**
   * 当前编辑的 Provider。
   */
  provider: ProviderInfo | null;
  /**
   * 是否正在保存。
   */
  loading: boolean;
  /**
   * 弹窗开关回调。
   */
  onOpenChange: (open: boolean) => void;
  /**
   * 表单提交回调。
   */
  onSubmit: (payload: ProviderPayload) => void;
}

/**
 * 构建执行器表单默认值。
 */
function toFormValues(provider: ProviderInfo | null): ProviderFormValues {
  if (!provider) {
    return {
      name: "",
      code: "",
      enabled: true,
    };
  }
  return {
    name: provider.name,
    code: provider.code,
    enabled: provider.enabled,
  };
}

/**
 * Provider 表单弹窗。
 */
export function ProviderFormDialog({
  open,
  provider,
  loading,
  onOpenChange,
  onSubmit,
}: ProviderFormDialogProps): JSX.Element {
  const form = useForm<ProviderFormValues>({
    resolver: zodResolver(providerFormSchema) as Resolver<ProviderFormValues>,
    defaultValues: toFormValues(provider),
    mode: "onChange",
  });

  useEffect(() => {
    if (!open) return;
    form.reset(toFormValues(provider));
  }, [form, open, provider]);

  /**
   * 提交 Provider 表单。
   */
  function handleSubmit(values: ProviderFormValues): void {
    onSubmit(toProviderPayload(values));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{provider ? "编辑执行器" : "新建执行器"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div className="grid gap-4">
            <Field
              label="执行器名称"
              required
              inline
              error={Boolean(form.formState.errors.name)}
              errorMessage={form.formState.errors.name?.message}
            >
              <Input
                {...form.register("name")}
                placeholder="例如: template 或 custom-template"
                required
                disabled={Boolean(provider)}
              />
            </Field>
            <div className="grid gap-1.5">
              <div className="grid h-9 grid-cols-[6rem_minmax(0,1fr)] items-center gap-2">
                <span className="field-label whitespace-nowrap">状态</span>
                <Controller
                  control={form.control}
                  name="enabled"
                  render={({ field }) => (
                    <Switch checked={field.value} onCheckedChange={field.onChange} className="justify-self-start" />
                  )}
                />
              </div>
            </div>
          </div>

          <Field
            label="Provider 代码"
            required
            error={Boolean(form.formState.errors.code)}
            errorMessage={form.formState.errors.code?.message}
          >
            <Controller
              control={form.control}
              name="code"
              render={({ field }) => (
                <CodeEditor
                  value={field.value}
                  onChange={field.onChange}
                  placeholder={`例如:\nclass TemplateProvider(BaseProvider):\n    name = "template"\n    config_schema = ProviderConfig\n\n    async def execute(self, config):\n        return ProviderResult.ok("执行成功")`}
                  rows={16}
                  required
                  aria-label="Provider 代码"
                />
              )}
            />
          </Field>

          <div className="mt-4 flex items-center justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" loading={loading}>
              保存
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
