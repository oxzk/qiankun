import { useEffect, useMemo } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm, type Resolver } from "react-hook-form";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { CheckboxGroup, type CheckboxOption } from "@/components/ui/checkbox-group";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useToast } from "@/hooks/use-toast";
import { getErrorMessage, notificationsApi, providersApi } from "@/lib/api";
import { getNextCronRuns } from "@/lib/cron";
import { formatDateTime } from "@/lib/datetime";
import { taskFormSchema, toTaskPayload, type TaskFormValues } from "@/lib/forms";
import { formatJson } from "@/lib/json-schema";
import { queryStaleTime } from "@/lib/query-options";
import { queryKeys } from "@/lib/query-keys";
import type { EnumMap, NotifyStrategy, Task, TaskPayload } from "@/types";
import { defaultTaskPayload, getNotifyStrategyOptions, toTaskDialogPayload } from "./task-utils";

export interface TaskDialogProps {
  /**
   * 是否显示弹窗。
   */
  open: boolean;
  /**
   * 正在编辑的任务。
   */
  task: Task | null;
  /**
   * 是否保存中。
   */
  loading: boolean;
  /**
   * 任务列表返回的枚举映射。
   */
  enums?: EnumMap;
  /**
   * 弹窗开关回调。
   */
  onOpenChange: (open: boolean) => void;
  /**
   * 表单提交回调。
   */
  onSubmit: (payload: TaskPayload) => void;
}

/**
 * 构建任务表单默认值。
 */
function toFormValues(task: Task | null): TaskFormValues {
  const payload = toTaskDialogPayload(task) ?? defaultTaskPayload;
  return {
    name: payload.name,
    provider_name: payload.provider_name,
    provider_config_text: formatJson(payload.provider_config || {}),
    cron_expression: payload.cron_expression,
    enabled: payload.enabled,
    timeout_seconds: payload.timeout_seconds,
    retry_count: payload.retry_count,
    retry_interval: payload.retry_interval,
    notification_ids: payload.notification_ids || [],
    notify_strategy: payload.notify_strategy,
  };
}

/**
 * 任务编辑弹窗。
 */
export function TaskDialog({ open, task, loading, enums, onOpenChange, onSubmit }: TaskDialogProps): JSX.Element {
  const { toast } = useToast();
  const form = useForm<TaskFormValues>({
    resolver: zodResolver(taskFormSchema) as Resolver<TaskFormValues>,
    defaultValues: toFormValues(task),
    mode: "onChange",
  });

  const providerName = form.watch("provider_name");
  const cronExpression = form.watch("cron_expression");
  const notifyStrategy = form.watch("notify_strategy");
  const providerConfigText = form.watch("provider_config_text");
  const debouncedCron = useDebouncedValue(cronExpression, 300);
  const debouncedConfigText = useDebouncedValue(providerConfigText, 300);

  const providersQuery = useQuery({
    queryKey: queryKeys.providers.options,
    queryFn: ({ signal }) => providersApi.list({ page: 1, page_size: 100, enabled: true }, signal),
    enabled: open,
    staleTime: queryStaleTime.catalog,
  });

  const notificationsQuery = useQuery({
    queryKey: queryKeys.notifications.options,
    queryFn: ({ signal }) => notificationsApi.list({ page: 1, page_size: 100 }, signal),
    enabled: open,
    staleTime: queryStaleTime.catalog,
  });

  const configMutation = useMutation({
    mutationFn: (name: string) => providersApi.config(name),
    onSuccess: (config, name) => {
      if (form.getValues("provider_name") !== name) return;
      form.setValue("provider_config_text", formatJson(config), { shouldValidate: true });
    },
    onError: (error) => {
      toast({
        title: "生成执行器配置失败",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    },
  });

  const providerOptions = useMemo(
    () => [
      { value: "", label: "请选择", disabled: true },
      ...(providersQuery.data?.items ?? []).map((item) => ({
        value: item.name,
        label: item.name,
      })),
    ],
    [providersQuery.data],
  );

  const notificationOptions: CheckboxOption[] = useMemo(
    () =>
      (notificationsQuery.data?.items ?? []).map((notification) => ({
        value: notification.id,
        label: notification.name,
      })),
    [notificationsQuery.data?.items],
  );

  const notifyStrategyOptions = useMemo(() => getNotifyStrategyOptions(enums), [enums]);
  const nextCronRuns = useMemo(() => getNextCronRuns(debouncedCron, 5), [debouncedCron]);
  const configError = form.formState.errors.provider_config_text?.message;

  useEffect(() => {
    if (!open) return;
    form.reset(toFormValues(task));
  }, [form, open, task]);

  useEffect(() => {
    if (!open) return;
    void form.trigger("provider_config_text");
  }, [debouncedConfigText, form, open]);

  /**
   * 切换执行器并拉取默认配置。
   */
  function handleProviderChange(name: string): void {
    form.setValue("provider_name", name, { shouldValidate: true, shouldDirty: true });
    form.setValue("provider_config_text", formatJson({}), { shouldValidate: true });
    if (name) configMutation.mutate(name);
  }

  /**
   * 提交任务表单。
   */
  function submit(values: TaskFormValues): void {
    onSubmit(toTaskPayload(values));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{task ? "编辑任务" : "新建任务"}</DialogTitle>
        </DialogHeader>
        <form
          className="flex min-h-0 flex-1 flex-col overflow-hidden"
          onSubmit={form.handleSubmit(submit)}
        >
          <DialogBody className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="任务名称" required error={Boolean(form.formState.errors.name)} errorMessage={form.formState.errors.name?.message}>
                <Input {...form.register("name")} required />
              </Field>
              <Field
                label="Cron 表达式"
                required
                error={Boolean(form.formState.errors.cron_expression)}
                errorMessage={form.formState.errors.cron_expression?.message}
              >
                <Input {...form.register("cron_expression")} required />
              </Field>
            </div>

            <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              <div className="mb-1 font-medium text-foreground">下次运行预览</div>
              {nextCronRuns.length ? (
                <ul className="space-y-0.5 font-mono">
                  {nextCronRuns.map((runAt) => (
                    <li key={runAt.toISOString()}>{formatDateTime(runAt)}</li>
                  ))}
                </ul>
              ) : (
                <div>无法解析当前 Cron 表达式, 请使用标准 5 段格式。</div>
              )}
            </div>

            <Field
              label="选择执行器"
              required
              error={Boolean(form.formState.errors.provider_name)}
              errorMessage={form.formState.errors.provider_name?.message}
            >
              {providersQuery.isLoading ? (
                <Skeleton className="h-10 w-full" />
              ) : (
                <Select
                  value={providerName}
                  onValueChange={handleProviderChange}
                  options={providerOptions}
                  placeholder="请选择"
                />
              )}
            </Field>

            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
              <Field label="超时秒数" required error={Boolean(form.formState.errors.timeout_seconds)}>
                <Input type="number" min={1} max={86400} {...form.register("timeout_seconds", { valueAsNumber: true })} required />
              </Field>
              <Field label="重试次数" required error={Boolean(form.formState.errors.retry_count)}>
                <Input type="number" min={0} max={10} {...form.register("retry_count", { valueAsNumber: true })} required />
              </Field>
              <Field label="重试间隔 (秒)" required error={Boolean(form.formState.errors.retry_interval)}>
                <Input type="number" min={1} max={86400} {...form.register("retry_interval", { valueAsNumber: true })} required />
              </Field>
              <div className="grid justify-self-end gap-1.5">
                <span className="field-label whitespace-nowrap">状态</span>
                <div className="flex h-9 items-center justify-end">
                  <Controller
                    control={form.control}
                    name="enabled"
                    render={({ field }) => (
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    )}
                  />
                </div>
              </div>
            </div>

            <Field label="执行器配置 (JSON)" error={Boolean(configError)} errorMessage={configError}>
              <Textarea
                {...form.register("provider_config_text")}
                placeholder={`例如:\n{\n  "message": "hello"\n}`}
                rows={7}
                className="font-mono text-xs"
                disabled={configMutation.isPending}
              />
            </Field>

            <fieldset className="grid gap-3 rounded-lg border p-3">
              <legend className="-ml-1 px-1 text-sm font-semibold text-muted-foreground">通知关联</legend>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="通知策略" required>
                  <Controller
                    control={form.control}
                    name="notify_strategy"
                    render={({ field }) => (
                      <Select
                        value={field.value}
                        onValueChange={(value) => {
                          const strategy = value as NotifyStrategy;
                          field.onChange(strategy);
                          if (strategy === "never") {
                            form.setValue("notification_ids", []);
                          }
                        }}
                        options={notifyStrategyOptions}
                      />
                    )}
                  />
                </Field>
                <Field label="通知渠道">
                  {notificationsQuery.isLoading ? (
                    <Skeleton className="h-10 w-full" />
                  ) : notifyStrategy === "never" ? (
                    <div className="flex h-10 items-center text-xs text-muted-foreground italic">不发送任何通知</div>
                  ) : (
                    <Controller
                      control={form.control}
                      name="notification_ids"
                      render={({ field }) => (
                        <CheckboxGroup
                          options={notificationOptions}
                          value={field.value}
                          onChange={(value) => field.onChange(value as number[])}
                          className="min-h-10"
                          orientation="horizontal"
                        />
                      )}
                    />
                  )}
                </Field>
              </div>
            </fieldset>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" loading={loading} disabled={Boolean(configError)}>
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
