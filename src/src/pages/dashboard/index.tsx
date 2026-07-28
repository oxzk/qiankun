import { useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, Clock3, PlayCircle, TimerOff } from "lucide-react";
import { EmptyState, SectionHeader } from "@/components/common";
import { DataTableShell } from "@/components/data/data-table-shell";
import { TableEmptyState } from "@/components/data/table-empty-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { executionsApi, getErrorMessage, statsApi, tasksApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime, formatDuration } from "@/lib/datetime";
import { executionStatusLabel, executionStatusVariant } from "@/pages/executions/status";

/**
 * 运维概览页面。
 */
export function DashboardPage(): JSX.Element {
  const statsQuery = useQuery({
    queryKey: queryKeys.stats.taskStats,
    queryFn: statsApi.getStats,
    staleTime: 15_000,
  });
  const tasksQuery = useQuery({
    queryKey: queryKeys.tasks.dashboard,
    queryFn: () => tasksApi.list({ page: 1, page_size: 6 }),
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });
  const executionsQuery = useQuery({
    queryKey: queryKeys.executions.dashboard,
    queryFn: () => executionsApi.list({ page: 1, page_size: 8 }),
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });
  const loading = statsQuery.isFetching || tasksQuery.isFetching || executionsQuery.isFetching;

  /**
   * 刷新概览数据。
   */
  function refresh(): void {
    void statsQuery.refetch();
    void tasksQuery.refetch();
    void executionsQuery.refetch();
  }

  const stats = statsQuery.data;

  const {
    successExecutions,
    failedExecutions,
    runningExecutions,
    totalExecutions,
    successRate,
  } = useMemo(() => {
    const statusMap = stats?.executions_by_status ?? {};
    const success = statusMap.success ?? 0;
    const failed = statusMap.failed ?? 0;
    const running = statusMap.running ?? 0;
    const timeout = statusMap.timeout ?? 0;
    const cancelled = statusMap.cancelled ?? 0;
    const total = success + failed + running + timeout + cancelled;
    const rate = total > 0 ? Math.round((success / total) * 100) : 0;
    return {
      successExecutions: success,
      failedExecutions: failed + timeout + cancelled,
      runningExecutions: running,
      totalExecutions: total,
      successRate: rate,
    };
  }, [stats]);

  return (
    <div className="space-y-6">
      <SectionHeader title="调度概览" description="集中查看任务状态, 执行质量和最近运行记录。" onRefresh={refresh} loading={loading} />
      {statsQuery.error ? <EmptyState title="统计加载失败" description={getErrorMessage(statsQuery.error)} /> : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statsQuery.isLoading ? (
          <MetricCardSkeleton />
        ) : (
          <>
            <MetricCard icon={<Activity className="h-4 w-4 text-primary" />} label="任务总数" value={stats?.total_tasks ?? 0} hint={`${stats?.active_tasks ?? 0} 个启用`} />
            <MetricCard icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />} label="成功执行" value={successExecutions} hint={`成功率 ${successRate}%`} />
            <MetricCard icon={<TimerOff className="h-4 w-4 text-destructive" />} label="异常执行" value={failedExecutions} hint={`${totalExecutions} 次总执行`} />
            <MetricCard icon={<PlayCircle className="h-4 w-4 text-amber-500" />} label="运行中" value={runningExecutions} hint="实时任务状态" />
          </>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">近期任务</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {tasksQuery.isLoading ? <DashboardTaskSkeleton /> : null}
              {(tasksQuery.data?.items ?? []).map((task) => (
                <div key={task.id} className="rounded-lg border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{task.name}</div>
                      <div className="mt-1 font-mono text-xs text-muted-foreground">{task.cron_expression}</div>
                    </div>
                    <Badge variant={task.enabled ? "default" : "secondary"}>{task.enabled ? "启用" : "停用"}</Badge>
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock3 className="h-3.5 w-3.5" />
                    下次运行: {formatDateTime(task.next_run_time)}
                  </div>
                </div>
              ))}
              {!tasksQuery.isLoading && !tasksQuery.data?.items.length ? <EmptyState title="暂无任务" description="创建任务后会显示在这里。" /> : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">最近执行</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTableShell>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>任务</th>
                    <th>状态</th>
                    <th>开始时间</th>
                    <th>耗时</th>
                  </tr>
                </thead>
                <tbody>
                  {executionsQuery.isLoading ? <DashboardExecutionSkeleton /> : null}
                  {(executionsQuery.data?.items ?? []).map((item) => (
                    <tr key={item.id}>
                      <td className="max-w-[14rem] truncate">
                        {item.task_name || item.provider_name || `#${item.task_id}`}
                      </td>
                      <td>
                        <Badge variant={executionStatusVariant(item.status)}>
                          {executionStatusLabel(item.status, executionsQuery.data?.enums)}
                        </Badge>
                      </td>
                      <td>{formatDateTime(item.started_at)}</td>
                      <td>{formatDuration(item.duration_ms !== null ? Math.round(item.duration_ms / 1000) : null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!executionsQuery.isLoading && !executionsQuery.data?.items.length ? (
                <TableEmptyState title="暂无执行记录" />
              ) : null}
            </DataTableShell>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/**
 * 指标卡片。
 */
function MetricCard({ icon, label, value, hint }: { icon: JSX.Element; label: string; value: number; hint: string }): JSX.Element {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">{icon}</div>
        <div className="min-w-0">
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
          <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * 指标卡片骨架屏。
 */
function MetricCardSkeleton(): JSX.Element {
  return (
    <>
      {Array.from({ length: 4 }).map((_, index) => (
        <Card key={index}>
          <CardContent className="flex items-center gap-4 p-5">
            <Skeleton className="h-10 w-10 shrink-0 rounded-lg" />
            <div className="min-w-0 flex-1">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="mt-2 h-7 w-14" />
              <Skeleton className="mt-2 h-3 w-24" />
            </div>
          </CardContent>
        </Card>
      ))}
    </>
  );
}

/**
 * 仪表盘任务骨架屏。
 */
function DashboardTaskSkeleton(): JSX.Element {
  return (
    <>
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="rounded-lg border p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="mt-2 h-4 w-24" />
            </div>
            <Skeleton className="h-6 w-14" />
          </div>
          <Skeleton className="mt-4 h-4 w-48" />
        </div>
      ))}
    </>
  );
}

/**
 * 仪表盘执行记录骨架屏。
 */
function DashboardExecutionSkeleton(): JSX.Element {
  return (
    <>
      {Array.from({ length: 6 }).map((_, index) => (
        <tr key={index}>
          <td>
            <Skeleton className="h-4 w-32" />
          </td>
          <td>
            <Skeleton className="h-6 w-16" />
          </td>
          <td>
            <Skeleton className="h-4 w-40" />
          </td>
          <td>
            <Skeleton className="h-4 w-16" />
          </td>
        </tr>
      ))}
    </>
  );
}
