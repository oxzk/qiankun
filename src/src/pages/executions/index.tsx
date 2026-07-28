import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Eye, Search } from "lucide-react";
import { EmptyState, SectionHeader, TooltipIconButton } from "@/components/common";
import { DataTableShell } from "@/components/data/data-table-shell";
import { PaginationBar } from "@/components/data/pagination-bar";
import { TableEmptyState } from "@/components/data/table-empty-state";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePagination } from "@/hooks/use-pagination";
import { useUrlStringParam } from "@/hooks/use-url-state";
import { getErrorMessage, executionsApi } from "@/lib/api";
import { enumOptions } from "@/lib/enums";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime, formatDuration } from "@/lib/datetime";
import { executionStatusLabel, executionStatusVariant, triggerTypeLabel } from "@/pages/executions/status";
import type { ExecutionStatus } from "@/types";

/**
 * 执行记录页面。
 */
export function ExecutionsPage(): JSX.Element {
  const [taskId, setTaskId] = useUrlStringParam("task_id");
  const [taskName, setTaskName] = useUrlStringParam("task_name");
  const [status, setStatus] = useUrlStringParam("status");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const debouncedTaskId = useDebouncedValue(taskId, 300);
  const debouncedTaskName = useDebouncedValue(taskName, 300);
  const statusFilter = (status as ExecutionStatus | "") || "";
  const { page, setPage } = usePagination([debouncedTaskId, debouncedTaskName, statusFilter]);

  const query = useQuery({
    queryKey: queryKeys.executions.list({
      page,
      taskId: debouncedTaskId,
      taskName: debouncedTaskName,
      status: statusFilter,
    }),
    queryFn: () =>
      executionsApi.list({
        page,
        page_size: 20,
        task_id: debouncedTaskId ? Number(debouncedTaskId) : "",
        task_name: debouncedTaskName,
        status: statusFilter,
      }),
    staleTime: 10_000,
    placeholderData: keepPreviousData,
    refetchInterval: (current) => {
      if (statusFilter === "running") return 3000;
      const hasRunning = (current.state.data?.items ?? []).some((item) => item.status === "running");
      return hasRunning ? 3000 : false;
    },
  });

  const detailQuery = useQuery({
    queryKey: queryKeys.executions.detail(selectedId ?? 0),
    queryFn: () => executionsApi.get(selectedId as number),
    enabled: selectedId !== null,
  });

  const statusOptions = useMemo(
    () => [{ value: "", label: "全部状态" }, ...enumOptions<ExecutionStatus>(query.data?.enums, "status")],
    [query.data?.enums],
  );

  const selected = detailQuery.data;

  return (
    <div className="space-y-4">
      <SectionHeader
        title="执行记录"
        description="查询任务运行历史, 日志和错误信息。"
        loading={query.isFetching}
        onRefresh={() => {
          void query.refetch();
        }}
      />
      {query.error ? <EmptyState title="执行记录加载失败" description={getErrorMessage(query.error)} /> : null}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-end">
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
      </div>
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
              <th className="text-right">详情</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <ExecutionTableSkeleton /> : null}
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
                <td>{formatDuration(item.duration_ms !== null ? Math.round(item.duration_ms / 1000) : null)}</td>
                <td className="text-right">
                  <div className="flex justify-end">
                    <TooltipIconButton label="查看详情" variant="ghost" onClick={() => setSelectedId(item.id)}>
                      <Eye className="h-4 w-4" />
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
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
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
                  <span>
                    {formatDuration(selected?.duration_ms != null ? Math.round(selected.duration_ms / 1000) : null)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">重试次数: </span>
                  <span>{selected?.retry_attempt ?? 0} 次</span>
                </div>
              </div>

              <div>
                <div className="field-label mb-2">日志</div>
                <pre className="code-block">{selected?.logs.length ? selected.logs.join("\n") : "暂无日志"}</pre>
              </div>

              {selected?.error_message ? (
                <div>
                  <div className="field-label mb-2 text-destructive">错误消息</div>
                  <pre className="code-block border-destructive/20 bg-destructive/5 text-destructive">
                    {selected.error_message}
                  </pre>
                </div>
              ) : null}

              {selected?.error_traceback ? (
                <div>
                  <div className="field-label mb-2 text-destructive">错误堆栈</div>
                  <pre className="code-block border-destructive/20 bg-destructive/5 text-xs text-destructive max-h-60 overflow-y-auto font-mono">
                    {selected.error_traceback}
                  </pre>
                </div>
              ) : null}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

/**
 * 执行记录表格骨架屏。
 */
function ExecutionTableSkeleton(): JSX.Element {
  return (
    <>
      {Array.from({ length: 10 }).map((_, index) => (
        <tr key={index}>
          <td>
            <Skeleton className="h-4 w-12" />
          </td>
          <td>
            <Skeleton className="h-4 w-36" />
          </td>
          <td>
            <Skeleton className="h-4 w-24" />
          </td>
          <td>
            <Skeleton className="h-6 w-16" />
          </td>
          <td>
            <Skeleton className="h-4 w-12" />
          </td>
          <td>
            <Skeleton className="h-4 w-40" />
          </td>
          <td>
            <Skeleton className="h-4 w-40" />
          </td>
          <td>
            <Skeleton className="h-4 w-16" />
          </td>
          <td className="text-right">
            <div className="flex justify-end">
              <Skeleton className="h-8 w-8 rounded-md" />
            </div>
          </td>
        </tr>
      ))}
    </>
  );
}
