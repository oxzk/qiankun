import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ConfirmDialog, EmptyState, SectionHeader } from "@/components/common";
import { PaginationBar } from "@/components/data/pagination-bar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePagination } from "@/hooks/use-pagination";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { useUrlStringParam } from "@/hooks/use-url-state";
import { getErrorMessage, tasksApi, executionsApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { Task, TaskPayload } from "@/types";
import { TaskDialog } from "./task-dialog";
import { TaskTable } from "./task-table";

type TaskAction = "run" | "cancel" | "delete" | "toggle";
type TaskActionResult = Task | boolean | null;

interface ConfirmState {
  /**
   * 待确认任务。
   */
  task: Task;
  /**
   * 待确认操作。
   */
  action: Extract<TaskAction, "cancel" | "delete">;
}

/**
 * 任务管理页面。
 */
export function TasksPage(): JSX.Element {
  const [name, setName] = useUrlStringParam("q");
  const [enabledParam, setEnabledParam] = useUrlStringParam("enabled");
  const enabledFilter: boolean | "" = enabledParam === "true" ? true : enabledParam === "false" ? false : "";
  const [editing, setEditing] = useState<Task | null>(null);
  const [open, setOpen] = useState(false);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [optimisticRunningTaskIds, setOptimisticRunningTaskIds] = useState<Set<number>>(new Set());
  const debouncedName = useDebouncedValue(name, 300);
  const { page, setPage } = usePagination([debouncedName, enabledFilter]);
  const navigate = useNavigate();

  const query = useQuery({
    queryKey: queryKeys.tasks.list({ page, name: debouncedName, enabled: enabledFilter }),
    queryFn: () =>
      tasksApi.list({
        page,
        page_size: 20,
        enabled: enabledFilter,
        name: debouncedName.trim() || undefined,
      }),
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });

  const runningQuery = useQuery({
    queryKey: queryKeys.executions.running,
    queryFn: () => executionsApi.list({ status: "running", page_size: 100 }),
    staleTime: 3_000,
    refetchInterval: (current) => ((current.state.data?.items?.length ?? 0) > 0 || optimisticRunningTaskIds.size > 0 ? 3000 : false),
  });

  const serverRunningTaskIds = useMemo(() => {
    return new Set((runningQuery.data?.items ?? []).map((item) => item.task_id));
  }, [runningQuery.data]);

  const runningTaskIds = useMemo(() => {
    return new Set([...serverRunningTaskIds, ...optimisticRunningTaskIds]);
  }, [serverRunningTaskIds, optimisticRunningTaskIds]);

  useEffect(() => {
    setOptimisticRunningTaskIds((current) => {
      const next = new Set([...current].filter((taskId) => serverRunningTaskIds.has(taskId)));
      return next.size === current.size ? current : next;
    });
  }, [serverRunningTaskIds]);

  const saveMutation = useToastMutation<Task, TaskPayload>({
    mutationFn: (payload: TaskPayload) => (editing ? tasksApi.update(editing.id, payload) : tasksApi.create(payload)),
    successTitle: () => (editing ? "任务已更新" : "任务已创建"),
    errorTitle: "保存失败",
    invalidate: [queryKeys.tasks.root, queryKeys.stats.taskStats],
    onSuccess: () => {
      setOpen(false);
      setEditing(null);
    },
  });

  const actionMutation = useToastMutation<TaskActionResult, { task: Task; action: TaskAction; enabled?: boolean }>({
    mutationFn: ({ task, action, enabled }) => {
      if (action === "run") return tasksApi.run(task.id);
      if (action === "cancel") return tasksApi.cancel(task.id);
      if (action === "toggle") {
        return enabled ? tasksApi.enable(task.id) : tasksApi.disable(task.id);
      }
      return tasksApi.delete(task.id);
    },
    successTitle: (_, variables) => taskActionSuccessTitle(variables.action, variables.enabled),
    errorTitle: "操作失败",
    invalidate: [queryKeys.tasks.root, queryKeys.executions.root, queryKeys.stats.taskStats],
    onSuccess: (result, variables) => {
      if (variables.action === "cancel" || variables.action === "delete" || result === false) {
        setOptimisticRunningTaskIds((current) => {
          const next = new Set(current);
          next.delete(variables.task.id);
          return next;
        });
      }
      setConfirmState(null);
    },
    onError: (_, variables) => {
      if (variables.action === "run") {
        setOptimisticRunningTaskIds((current) => {
          const next = new Set(current);
          next.delete(variables.task.id);
          return next;
        });
      }
    },
  });

  const pendingTaskId =
    actionMutation.isPending && actionMutation.variables ? actionMutation.variables.task.id : null;

  /**
   * 打开创建任务弹窗。
   */
  function createTask(): void {
    setEditing(null);
    setOpen(true);
  }

  /**
   * 跳转到当前任务的执行记录。
   */
  function openExecutions(task: Task): void {
    navigate(`/executions?task_id=${task.id}`);
  }

  /**
   * 执行已确认的任务操作。
   */
  function runConfirmedAction(): void {
    if (!confirmState) return;
    actionMutation.mutate({ task: confirmState.task, action: confirmState.action });
  }

  /**
   * 更新启用筛选。
   */
  function setEnabledFilter(value: boolean | ""): void {
    if (value === "") setEnabledParam("");
    else setEnabledParam(String(value));
  }

  return (
    <div className="space-y-4">
      <SectionHeader
        title="任务管理"
        description="维护 cron 调度任务, 控制启停和手动执行。"
        loading={query.isFetching || runningQuery.isFetching}
        onRefresh={() => {
          void query.refetch();
          void runningQuery.refetch();
        }}
        actions={
          <Button size="sm" onClick={createTask}>
            <Plus className="h-4 w-4 mr-1" />
            新建任务
          </Button>
        }
      />

      {query.error ? <EmptyState title="任务加载失败" description={getErrorMessage(query.error)} /> : null}

      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-end">
        <div className="relative md:w-80">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="按任务名过滤" className="pl-9" />
        </div>
        <Select
          value={String(enabledFilter)}
          onValueChange={(value) => setEnabledFilter(value === "" ? "" : value === "true")}
          options={[
            { value: "", label: "全部状态" },
            { value: "true", label: "启用" },
            { value: "false", label: "停用" },
          ]}
          className="md:w-36"
        />
      </div>

      <TaskTable
        tasks={query.data?.items ?? []}
        loading={query.isLoading}
        runningTaskIds={runningTaskIds}
        pendingTaskId={pendingTaskId}
        onToggle={(task, enabled) => actionMutation.mutate({ task, action: "toggle", enabled })}
        onExecute={(task) => {
          setOptimisticRunningTaskIds((current) => new Set(current).add(task.id));
          actionMutation.mutate({ task, action: "run" });
        }}
        onCancel={(task) => setConfirmState({ task, action: "cancel" })}
        onExecutions={openExecutions}
        onEdit={(task) => {
          setEditing(task);
          setOpen(true);
        }}
        onDelete={(task) => setConfirmState({ task, action: "delete" })}
      />

      <PaginationBar page={query.data?.page ?? page} pageSize={query.data?.page_size} total={query.data?.total} onPageChange={setPage} />

      <TaskDialog
        open={open}
        task={editing}
        loading={saveMutation.isPending}
        enums={query.data?.enums}
        onOpenChange={(isOpen) => {
          setOpen(isOpen);
          if (!isOpen) setEditing(null);
        }}
        onSubmit={(payload) => saveMutation.mutate(payload)}
      />

      <ConfirmDialog
        open={Boolean(confirmState)}
        title={confirmState?.action === "delete" ? "删除任务" : "取消任务"}
        description={
          confirmState?.action === "delete"
            ? `确认删除任务 "${confirmState.task.name}"? 相关执行记录也会被删除。`
            : `确认取消任务 "${confirmState?.task.name}" 的当前执行?`
        }
        confirmText={confirmState?.action === "delete" ? "删除" : "取消任务"}
        loading={actionMutation.isPending}
        onOpenChange={(isOpen) => {
          if (!isOpen) setConfirmState(null);
        }}
        onConfirm={runConfirmedAction}
      />
    </div>
  );
}

/**
 * 返回任务操作成功提示。
 */
function taskActionSuccessTitle(action: TaskAction, enabled?: boolean): string {
  if (action === "run") return "已触发运行";
  if (action === "cancel") return "已发送取消请求";
  if (action === "toggle") return enabled ? "任务已启用" : "任务已停用";
  return "任务已删除";
}
