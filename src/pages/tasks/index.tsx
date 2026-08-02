import { useCallback, useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ConfirmDialog, EmptyState, FilterBar, PaginationBar, SectionHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useTableParams } from "@/hooks/use-table-params";
import { useToast } from "@/hooks/use-toast";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { executionsApi, getErrorMessage, tasksApi } from "@/lib/api";
import { queryStaleTime } from "@/lib/query-options";
import { queryKeys } from "@/lib/query-keys";
import type { Task, TaskPayload } from "@/types";
import { TaskDialog } from "./task-dialog";
import { TaskTable } from "./task-table";

type TaskAction = "run" | "cancel" | "delete";

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
  const { filters, debouncedFilters, setFilter, resetFilters, page, setPage } = useTableParams({
    defaultFilters: {
      q: "",
      enabled: "" as "true" | "false" | "",
    },
    debounceKeys: ["q"],
  });

  const enabledFilter: boolean | "" =
    debouncedFilters.enabled === "true" ? true : debouncedFilters.enabled === "false" ? false : "";

  const [editing, setEditing] = useState<Task | null>(null);
  const [open, setOpen] = useState(false);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [optimisticRunningTaskIds, setOptimisticRunningTaskIds] = useState<Set<number>>(new Set());

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const query = useQuery({
    queryKey: queryKeys.tasks.list({ page, name: debouncedFilters.q, enabled: enabledFilter }),
    queryFn: ({ signal }) =>
      tasksApi.list(
        {
          page,
          page_size: 20,
          enabled: enabledFilter,
          name: debouncedFilters.q.trim() || undefined,
        },
        signal,
      ),
    staleTime: queryStaleTime.list,
    placeholderData: keepPreviousData,
  });

  const runningQuery = useQuery({
    queryKey: queryKeys.executions.running,
    queryFn: ({ signal }) => executionsApi.list({ status: "running", page_size: 100 }, signal),
    staleTime: queryStaleTime.realtime,
    refetchInterval: (q) => ((q.state.data?.items?.length ?? 0) > 0 ? 3000 : false),
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

  // 开关启停操作的乐观更新
  const toggleMutation = useMutation({
    mutationFn: ({ task, enabled }: { task: Task; enabled: boolean }) =>
      enabled ? tasksApi.enable(task.id) : tasksApi.disable(task.id),
    onMutate: async ({ task, enabled }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.root });
      const previousQueries = queryClient.getQueriesData({ queryKey: queryKeys.tasks.root });

      queryClient.setQueriesData({ queryKey: queryKeys.tasks.root }, (old: unknown) => {
        if (!old || typeof old !== "object" || !("items" in old) || !Array.isArray((old as { items: Task[] }).items)) {
          return old;
        }
        return {
          ...old,
          items: (old as { items: Task[] }).items.map((item) =>
            item.id === task.id ? { ...item, enabled } : item,
          ),
        };
      });

      return { previousQueries };
    },
    onError: (err, _, context) => {
      if (context?.previousQueries) {
        context.previousQueries.forEach(([key, data]) => {
          queryClient.setQueryData(key, data);
        });
      }
      toast({ title: "操作失败", description: getErrorMessage(err), variant: "destructive" });
    },
    onSuccess: (_, variables) => {
      toast({ title: variables.enabled ? "任务已启用" : "任务已停用" });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tasks.root });
      void queryClient.invalidateQueries({ queryKey: queryKeys.stats.taskStats });
    },
  });

  const actionMutation = useToastMutation<unknown, { task: Task; action: TaskAction }>({
    mutationFn: ({ task, action }) => {
      if (action === "run") return tasksApi.run(task.id);
      if (action === "cancel") return tasksApi.cancel(task.id);
      return tasksApi.delete(task.id);
    },
    successTitle: (_, variables) => (variables.action === "run" ? "已触发运行" : variables.action === "cancel" ? "已发送取消请求" : "任务已删除"),
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
    actionMutation.isPending && actionMutation.variables
      ? actionMutation.variables.task.id
      : toggleMutation.isPending && toggleMutation.variables
        ? toggleMutation.variables.task.id
        : null;

  const handleToggle = useCallback(
    (task: Task, enabled: boolean) => {
      toggleMutation.mutate({ task, enabled });
    },
    [toggleMutation],
  );

  const handleExecute = useCallback(
    (task: Task) => {
      setOptimisticRunningTaskIds((current) => new Set(current).add(task.id));
      actionMutation.mutate({ task, action: "run" });
    },
    [actionMutation],
  );

  const handleCancel = useCallback((task: Task) => {
    setConfirmState({ task, action: "cancel" });
  }, []);

  const handleEdit = useCallback((task: Task) => {
    setEditing(task);
    setOpen(true);
  }, []);

  const handleDelete = useCallback((task: Task) => {
    setConfirmState({ task, action: "delete" });
  }, []);

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
  const openExecutions = useCallback(
    (task: Task) => {
      navigate(`/executions?task_id=${task.id}`);
    },
    [navigate],
  );

  /**
   * 执行已确认的任务操作。
   */
  function runConfirmedAction(): void {
    if (!confirmState) return;
    actionMutation.mutate({ task: confirmState.task, action: confirmState.action });
  }

  const hasActiveFilters = Boolean(filters.q || filters.enabled);

  return (
    <div className="space-y-4">
      <SectionHeader
        title="任务管理"
        description="维护 cron 调度任务, 控制启停和手动执行。"
        loading={query.isFetching || runningQuery.isFetching}
        onRefresh={() => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.tasks.root });
          void queryClient.invalidateQueries({ queryKey: queryKeys.executions.running });
        }}
        actions={
          <Button size="sm" onClick={createTask}>
            <Plus className="mr-1 h-4 w-4" />
            新建任务
          </Button>
        }
      />

      {query.error ? <EmptyState title="任务加载失败" description={getErrorMessage(query.error)} /> : null}

      <FilterBar hasActiveFilters={hasActiveFilters} onClear={resetFilters}>
        <div className="relative md:w-80">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={filters.q}
            onChange={(event) => setFilter("q", event.target.value)}
            placeholder="按任务名过滤"
            className="pl-9"
          />
        </div>
        <Select
          value={filters.enabled}
          onValueChange={(value) => setFilter("enabled", value as "true" | "false" | "")}
          options={[
            { value: "", label: "全部状态" },
            { value: "true", label: "启用" },
            { value: "false", label: "停用" },
          ]}
          className="md:w-36"
        />
      </FilterBar>

      <TaskTable
        tasks={query.data?.items ?? []}
        loading={query.isLoading}
        runningTaskIds={runningTaskIds}
        pendingTaskId={pendingTaskId}
        onToggle={handleToggle}
        onExecute={handleExecute}
        onCancel={handleCancel}
        onExecutions={openExecutions}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <PaginationBar
        page={query.data?.page ?? page}
        pageSize={query.data?.page_size}
        total={query.data?.total}
        onChange={setPage}
      />

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
