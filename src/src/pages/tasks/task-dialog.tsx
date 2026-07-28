import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { CheckboxGroup, type CheckboxOption } from "@/components/ui/checkbox-group";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
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
import { formatJson, parseJsonObject, tryParseJsonObject } from "@/lib/json-schema";
import { queryKeys } from "@/lib/query-keys";
import type { EnumMap, JsonRecord, NotifyStrategy, Task, TaskPayload } from "@/types";
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
 * 任务编辑弹窗。
 */
export function TaskDialog({ open, task, loading, enums, onOpenChange, onSubmit }: TaskDialogProps): JSX.Element {
  const [payload, setPayload] = useState<TaskPayload>(defaultTaskPayload);
  const [providerConfigText, setProviderConfigText] = useState(formatJson({}));
  const [providerError, setProviderError] = useState(false);
  const { toast } = useToast();
  const debouncedConfigText = useDebouncedValue(providerConfigText, 300);
  const debouncedCron = useDebouncedValue(payload.cron_expression, 300);

  const providersQuery = useQuery({
    queryKey: queryKeys.providers.root,
    queryFn: () => providersApi.list({ page: 1, page_size: 500, enabled: true }),
    enabled: open,
    staleTime: 60_000,
  });

  const notificationsQuery = useQuery({
    queryKey: queryKeys.notifications.root,
    queryFn: () => notificationsApi.list({ page: 1, page_size: 500 }),
    enabled: open,
    staleTime: 60_000,
  });

  const configMutation = useMutation({
    mutationFn: (providerName: string) => providersApi.config(providerName),
    onSuccess: (config, providerName) => {
      setPayload((current) => {
        if (current.provider_name !== providerName) return current;
        setProviderConfigText(formatJson(config));
        return {
          ...current,
          provider_config: config,
        };
      });
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

  const configParseError = useMemo(() => tryParseJsonObject(debouncedConfigText).error, [debouncedConfigText]);

  const nextCronRuns = useMemo(() => getNextCronRuns(debouncedCron, 5), [debouncedCron]);

  useEffect(() => {
    if (open) {
      const nextPayload = toTaskDialogPayload(task);
      setPayload(nextPayload);
      setProviderConfigText(formatJson(nextPayload.provider_config || {}));
      setProviderError(false);
    }
  }, [task, open]);

  /**
   * 切换执行器并拉取默认配置。
   */
  function handleProviderChange(name: string): void {
    setProviderError(false);
    const nextConfig = {};
    setPayload({
      ...payload,
      provider_name: name,
      provider_config: nextConfig,
    });
    setProviderConfigText(formatJson(nextConfig));
    if (name) configMutation.mutate(name);
  }

  /**
   * 提交任务表单。
   */
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!payload.provider_name) {
      setProviderError(true);
      return;
    }
    let providerConfig: JsonRecord;
    try {
      providerConfig = parseJsonObject(providerConfigText);
    } catch (error) {
      toast({
        title: "JSON 格式错误",
        description: error instanceof Error ? error.message : "请输入有效的 JSON 对象格式。",
        variant: "destructive",
      });
      return;
    }
    onSubmit({
      ...payload,
      provider_config: providerConfig,
      notification_ids: payload.notification_ids || [],
    });
  }

  /**
   * 原生必填校验拦截提交时同步显示执行器错误。
   */
  function handleInvalid(): void {
    if (!payload.provider_name) {
      setProviderError(true);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{task ? "编辑任务" : "新建任务"}</DialogTitle>
        </DialogHeader>
        <form className="grid gap-7" onSubmit={submit} onInvalidCapture={handleInvalid}>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="任务名称" required>
              <Input value={payload.name} onChange={(event) => setPayload({ ...payload, name: event.target.value })} required />
            </Field>
            <Field label="Cron 表达式" required>
              <Input
                value={payload.cron_expression}
                onChange={(event) => setPayload({ ...payload, cron_expression: event.target.value })}
                required
              />
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

          <Field label="选择执行器" required error={providerError}>
            {providersQuery.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <Select
                value={payload.provider_name}
                onValueChange={handleProviderChange}
                options={providerOptions}
                placeholder="请选择"
              />
            )}
          </Field>

          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
            <Field label="超时秒数" required>
              <Input
                type="number"
                min={1}
                max={86400}
                value={payload.timeout_seconds}
                onChange={(event) => setPayload({ ...payload, timeout_seconds: Number(event.target.value) })}
                required
              />
            </Field>
            <Field label="重试次数" required>
              <Input
                type="number"
                min={0}
                max={10}
                value={payload.retry_count}
                onChange={(event) => setPayload({ ...payload, retry_count: Number(event.target.value) })}
                required
              />
            </Field>
            <Field label="重试间隔 (秒)" required>
              <Input
                type="number"
                min={1}
                max={86400}
                value={payload.retry_interval}
                onChange={(event) => setPayload({ ...payload, retry_interval: Number(event.target.value) })}
                required
              />
            </Field>
            <div className="grid justify-self-end gap-1.5">
              <span className="field-label whitespace-nowrap">状态</span>
              <div className="flex h-9 items-center justify-end">
                <Switch checked={payload.enabled} onCheckedChange={(checked) => setPayload({ ...payload, enabled: checked })} />
              </div>
            </div>
          </div>

          <Field label="执行器配置 (JSON)" error={Boolean(configParseError)} errorMessage={configParseError || undefined}>
            <Textarea
              value={providerConfigText}
              onChange={(event) => setProviderConfigText(event.target.value)}
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
                <Select
                  value={payload.notify_strategy}
                  onValueChange={(value) => {
                    const strategy = value as NotifyStrategy;
                    setPayload({
                      ...payload,
                      notify_strategy: strategy,
                      notification_ids: strategy === "never" ? [] : payload.notification_ids,
                    });
                  }}
                  options={notifyStrategyOptions}
                />
              </Field>
              <Field label="通知渠道">
                {notificationsQuery.isLoading ? (
                  <Skeleton className="h-10 w-full" />
                ) : payload.notify_strategy === "never" ? (
                  <div className="flex h-10 items-center text-xs text-muted-foreground italic">不发送任何通知</div>
                ) : (
                  <CheckboxGroup
                    options={notificationOptions}
                    value={payload.notification_ids}
                    onChange={(value) => setPayload({ ...payload, notification_ids: value as number[] })}
                    className="min-h-10"
                    orientation="horizontal"
                  />
                )}
              </Field>
            </div>
          </fieldset>
          <div className="flex justify-end gap-2 mt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" loading={loading} disabled={Boolean(configParseError)}>
              保存
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
