import { History, Pencil, Play, Square, Trash2 } from "lucide-react";
import { TooltipIconButton } from "@/components/common";
import { DataTableShell } from "@/components/data/data-table-shell";
import { TableEmptyState } from "@/components/data/table-empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { formatDateTime } from "@/lib/datetime";
import type { Task } from "@/types";

export interface TaskTableProps {
  /**
   * 任务列表。
   */
  tasks: Task[];
  /**
   * 是否首次加载中。
   */
  loading: boolean;
  /**
   * 正在运行的任务 ID 集合。
   */
  runningTaskIds: Set<number>;
  /**
   * 当前正在提交操作的任务 ID。
   */
  pendingTaskId: number | null;
  /**
   * 启停任务回调。
   */
  onToggle: (task: Task, enabled: boolean) => void;
  /**
   * 执行任务回调。
   */
  onExecute: (task: Task) => void;
  /**
   * 取消任务回调。
   */
  onCancel: (task: Task) => void;
  /**
   * 查看执行记录回调。
   */
  onExecutions: (task: Task) => void;
  /**
   * 编辑任务回调。
   */
  onEdit: (task: Task) => void;
  /**
   * 删除任务回调。
   */
  onDelete: (task: Task) => void;
}

/**
 * 任务列表表格。
 */
export function TaskTable({
  tasks,
  loading,
  runningTaskIds,
  pendingTaskId,
  onToggle,
  onExecute,
  onCancel,
  onExecutions,
  onEdit,
  onDelete,
}: TaskTableProps): JSX.Element {
  return (
    <DataTableShell>
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>任务</th>
            <th>执行器 (Provider)</th>
            <th>调度 (Cron)</th>
            <th>状态</th>
            <th>上次运行</th>
            <th>下次运行</th>
            <th>超时 / 重试</th>
            <th className="w-48 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {loading ? <TaskTableSkeleton /> : null}
          {tasks.map((task) => {
            const running = runningTaskIds.has(task.id);
            const rowPending = pendingTaskId === task.id;
            return (
              <tr key={task.id}>
                <td>#{task.id}</td>
                <td>
                  <div className="font-medium">{task.name}</div>
                </td>
                <td>
                  <code className="text-xs px-1.5 py-0.5 rounded bg-muted font-mono font-bold">
                    {task.provider_name}
                  </code>
                </td>
                <td className="font-mono text-xs">{task.cron_expression}</td>
                <td>
                  <div className="flex flex-wrap items-center gap-2">
                    <Switch
                      checked={task.enabled}
                      onCheckedChange={(checked) => onToggle(task, checked)}
                      disabled={rowPending}
                      aria-label={task.enabled ? "停用任务" : "启用任务"}
                    />
                    <span className="text-xs text-muted-foreground">
                      {running ? "运行中" : task.enabled ? "启用" : "停用"}
                    </span>
                  </div>
                </td>
                <td>{formatDateTime(task.last_run_time)}</td>
                <td>{formatDateTime(task.next_run_time)}</td>
                <td className="text-xs">
                  <div>{task.timeout_seconds}s 超时</div>
                  <div className="text-muted-foreground mt-0.5">
                    {task.retry_count > 0 ? `${task.retry_count}次 / ${task.retry_interval}s` : "无重试"}
                  </div>
                </td>
                <td className="text-right">
                  <div className="flex justify-end gap-1">
                    {running ? (
                      <TooltipIconButton
                        label="取消执行"
                        variant="ghost"
                        disabled={rowPending}
                        onClick={() => onCancel(task)}
                      >
                        <Square className="h-4 w-4" />
                      </TooltipIconButton>
                    ) : (
                      <TooltipIconButton
                        label="手动执行"
                        variant="ghost"
                        disabled={rowPending}
                        onClick={() => onExecute(task)}
                      >
                        <Play className="h-4 w-4" />
                      </TooltipIconButton>
                    )}
                    <TooltipIconButton label="执行记录" variant="ghost" onClick={() => onExecutions(task)}>
                      <History className="h-4 w-4" />
                    </TooltipIconButton>
                    <TooltipIconButton label="编辑" variant="ghost" onClick={() => onEdit(task)}>
                      <Pencil className="h-4 w-4" />
                    </TooltipIconButton>
                    <TooltipIconButton
                      label="删除"
                      variant="ghost"
                      disabled={rowPending}
                      onClick={() => onDelete(task)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </TooltipIconButton>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!loading && !tasks.length ? (
        <TableEmptyState title="暂无任务" description="点击新建任务开始配置调度。" />
      ) : null}
    </DataTableShell>
  );
}

/**
 * 任务表格骨架屏。
 */
function TaskTableSkeleton(): JSX.Element {
  return (
    <>
      {Array.from({ length: 8 }).map((_, index) => (
        <tr key={index}>
          <td>
            <Skeleton className="h-4 w-8" />
          </td>
          <td>
            <Skeleton className="h-4 w-32" />
          </td>
          <td>
            <Skeleton className="h-4 w-20" />
          </td>
          <td>
            <Skeleton className="h-4 w-24" />
          </td>
          <td>
            <Skeleton className="h-6 w-24" />
          </td>
          <td>
            <Skeleton className="h-4 w-36" />
          </td>
          <td>
            <Skeleton className="h-4 w-36" />
          </td>
          <td>
            <Skeleton className="h-4 w-24" />
          </td>
          <td className="text-right">
            <div className="flex justify-end gap-1">
              <Skeleton className="h-8 w-8 rounded-md" />
              <Skeleton className="h-8 w-8 rounded-md" />
              <Skeleton className="h-8 w-8 rounded-md" />
              <Skeleton className="h-8 w-8 rounded-md" />
            </div>
          </td>
        </tr>
      ))}
    </>
  );
}
