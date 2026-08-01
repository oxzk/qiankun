import { useMemo, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Search, Trash2 } from "lucide-react";
import {
  CodeBlock,
  ConfirmDialog,
  EmptyState,
  FilterBar,
  SectionHeader,
  TooltipIconButton,
} from "@/components/common";
import { DataTableShell } from "@/components/data/data-table-shell";
import { PaginationBar } from "@/components/data/pagination-bar";
import { TableEmptyState } from "@/components/data/table-empty-state";
import { TableSkeleton } from "@/components/data/table-skeleton";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePagination } from "@/hooks/use-pagination";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { useUrlParamsWriter, useUrlStringParam } from "@/hooks/use-url-state";
import { executionsApi, getErrorMessage } from "@/lib/api";
import { formatDateTime, formatDurationMs } from "@/lib/datetime";
import { enumOptions } from "@/lib/enums";
import { queryStaleTime } from "@/lib/query-options";
import { queryKeys } from "@/lib/query-keys";
import { executionStatusLabel, executionStatusVariant, triggerTypeLabel } from "@/pages/executions/status";
import type { ExecutionStatus } from "@/types";

const EXECUTION_SKELETON_COLUMNS = [
  { widthClass: "w-12" },
  { widthClass: "w-36" },
  { widthClass: "w-24" },
  { widthClass: "w-16" },
  { widthClass: "w-12" },
  { widthClass: "w-40" },
  { widthClass: "w-40" },
  { widthClass: "w-16" },
  { widthClass: "w-16", align: "right" as const },
];

/**
 * 解析任务 ID 筛选, 非法值返回空。
 */
function parseTaskIdFilter(raw: string): number | "" {
  if (!raw.trim()) return "";
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : "";
}

/**
 * 执行记录页面。
 */
export function ExecutionsPage(): JSX.Element {
  const [taskId, setTaskId] = useUrlStringParam("task_id");
  const [taskName, setTaskName] = useUrlStringParam("task_name");
  const [status, setStatus] = useUrlStringParam("status");
  const writeUrlParams = useUrlParamsWriter();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const debouncedTaskId = useDebouncedValue(taskId, 300);
  const debouncedTaskName = useDebouncedValue(taskName, 300);
  const statusFilter = (status as ExecutionStatus | "") || "";
  const parsedTaskId = parseTaskIdFilter(debouncedTaskId);
  const { page, setPage } = usePagination([debouncedTaskId, debouncedTaskName, statusFilter]);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: queryKeys.executions.list({
      page,
      taskId: debouncedTaskId,
      taskName: debouncedTaskName,
      status: statusFilter,
    }),
    queryFn: ({ signal }) =>
      executionsApi.list(
        {
          page,
          page_size: 20,
          task_id: parsedTaskId,
          task_name: debouncedTaskName,
          status: statusFilter,
        },
        signal,
      ),
    enabled: !debouncedTaskId || parsedTaskId !== "",
    staleTime: queryStaleTime.list,
    placeholderData: keepPreviousData,
  });

  const detailQuery = useQuery({
    queryKey: queryKeys.executions.detail(selectedId ?? 0),
    queryFn: ({ signal }) => executionsApi.get(selectedId as number, signal),
    enabled: selectedId !== null,
    staleTime: queryStaleTime.realtime,
  });

  const deleteMutation = useToastMutation<null, number>({
    mutationFn: (executionId) => executionsApi.delete(executionId),
    successTitle: "执行记录已删除",
    errorTitle: "删除执行记录失败",
    invalidate: [queryKeys.executions.root],
    onSuccess: (_data, executionId) => {
      if (selectedId === executionId) setSelectedId(null);
      setDeletingId(null);
    },
  });

  const statusOptions = useMemo(
    () => [{ value: "", label: "全部状态" }, ...enumOptions<ExecutionStatus>(query.data?.enums, "status")],
    [query.data?.enums],
  );

  const selected = detailQuery.data;
  const hasActiveFilters = Boolean(taskId || taskName || status);

  return (
    <div className="space-y-4">
      <SectionHeader
        title="执行记录"
        description="查询任务运行历史, 日志和错误信息。"
        loading={query.isFetching}
        onRefresh={() => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.executions.root });
        }}
      />
      {query.error ? <EmptyState title="执行记录加载失败" description={getErrorMessage(query.error)} /> : null}
      {debouncedTaskId && parsedTaskId === "" ? (
        <EmptyState title="任务 ID 无效" description="请输入正整数任务 ID, 或改用任务名称筛选。" />
      ) : null}
      <FilterBar
        hasActiveFilters={hasActiveFilters}
        onClear={() => writeUrlParams({ task_id: null, task_name: null, status: null, page: null })}
      >
        <div className="relative md:w-64">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={taskName}
            onChange={(event) => {
              setTaskName(event.target.value);
              setTaskId("");
            }}
            placeholder={taskId ? `任务 #${taskId}` : "按任务名称查询"}
            className="pl-9"
          />
        </div>
        <Select
          value={statusFilter}
          onValueChange={(value) => setStatus(value)}
          options={statusOptions}
          className="md:w-36"
        />
      </FilterBar>
      <DataTableShell>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>任务</th>
              <th>执行器</th>
              <th>状态</th>
              <th>重试次数</th>
              <th>开始时间</th>
              <th>结束时间</th>
              <th>耗时</th>
              <th className="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <TableSkeleton columns={EXECUTION_SKELETON_COLUMNS} rows={10} /> : null}
            {(query.data?.items ?? []).map((item) => (
              <tr key={item.id}>
                <td>#{item.id}</td>
                <td className="font-medium">{item.task_name || `任务 #${item.task_id}`}</td>
                <td>
                  <code className="text-xs">{item.provider_name}</code>
                </td>
                <td>
                  <Badge variant={executionStatusVariant(item.status)}>
                    {executionStatusLabel(item.status, query.data?.enums)}
                  </Badge>
                </td>
                <td>{item.retry_attempt > 0 ? `${item.retry_attempt} 次` : "-"}</td>
                <td>{formatDateTime(item.started_at)}</td>
                <td>{formatDateTime(item.finished_at)}</td>
                <td>{formatDurationMs(item.duration_ms)}</td>
                <td className="text-right">
                  <div className="flex justify-end gap-1">
                    <TooltipIconButton label="查看详情" variant="ghost" onClick={() => setSelectedId(item.id)}>
                      <Eye className="h-4 w-4" />
                    </TooltipIconButton>
                    <TooltipIconButton
                      label="删除"
                      variant="ghost"
                      onClick={() => setDeletingId(item.id)}
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </TooltipIconButton>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!query.isLoading && !query.data?.items.length ? <TableEmptyState title="暂无执行记录" /> : null}
      </DataTableShell>
      <PaginationBar
        page={query.data?.page ?? page}
        pageSize={query.data?.page_size}
        total={query.data?.total}
        onPageChange={setPage}
      />

      <Dialog open={selectedId !== null} onOpenChange={(open) => !open && setSelectedId(null)}>
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>执行详情 #{selectedId}</DialogTitle>
          </DialogHeader>
          {detailQuery.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-64" />
              <Skeleton className="h-32 w-full" />
            </div>
          ) : detailQuery.error ? (
            <EmptyState title="详情加载失败" description={getErrorMessage(detailQuery.error)} />
          ) : (
            <div className="grid gap-4">
              <div className="grid gap-3 text-sm md:grid-cols-2">
                <div>
                  <span className="text-muted-foreground">任务: </span>
                  <span className="font-medium">
                    {selected ? selected.task_name || `任务 #${selected.task_id}` : "-"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">执行器: </span>
                  <span className="font-mono text-xs">{selected?.provider_name}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">触发方式: </span>
                  <span>{selected ? triggerTypeLabel(selected.trigger_type, query.data?.enums) : "-"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">状态: </span>
                  {selected ? (
                    <Badge variant={executionStatusVariant(selected.status)}>
                      {executionStatusLabel(selected.status, query.data?.enums)}
                    </Badge>
                  ) : (
                    <span>-</span>
                  )}
                </div>
                <div>
                  <span className="text-muted-foreground">开始时间: </span>
                  <span>{formatDateTime(selected?.started_at)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">结束时间: </span>
                  <span>{formatDateTime(selected?.finished_at)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">执行耗时: </span>
                  <span>{formatDurationMs(selected?.duration_ms)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">重试次数: </span>
                  <span>{selected?.retry_attempt ?? 0} 次</span>
                </div>
              </div>

              <div>
                <div className="field-label mb-2">日志</div>
                <CodeBlock
                  content={(selected?.logs ?? []).join("\n")}
                  emptyText="暂无日志"
                  copyable={false}
                />
              </div>

              {selected?.error_message ? (
                <div>
                  <div className="mb-2 field-label text-destructive">错误消息</div>
                  <CodeBlock
                    content={selected.error_message}
                    copyable={false}
                    className="border-destructive/20 bg-destructive/5 text-destructive"
                  />
                </div>
              ) : null}

              {selected?.error_traceback ? (
                <div>
                  <div className="mb-2 field-label text-destructive">错误堆栈</div>
                  <CodeBlock
                    content={selected.error_traceback}
                    copyable={false}
                    className="max-h-60 border-destructive/20 bg-destructive/5 font-mono text-xs text-destructive"
                  />
                </div>
              ) : null}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deletingId !== null}
        onOpenChange={(open) => !open && setDeletingId(null)}
        title="删除执行记录"
        description={deletingId !== null ? `确认删除执行记录 #${deletingId}?` : ""}
        confirmText="删除"
        loading={deleteMutation.isPending}
        onConfirm={() => {
          if (deletingId !== null) deleteMutation.mutate(deletingId);
        }}
      />
    </div>
  );
}
