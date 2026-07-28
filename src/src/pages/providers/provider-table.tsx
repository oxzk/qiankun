import { Pencil, Play } from "lucide-react";
import { EmptyState, TooltipIconButton } from "@/components/common";
import { DataTableShell } from "@/components/data/data-table-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import type { ProviderInfo } from "@/types";

export interface ProviderTableProps {
  /**
   * Provider 列表。
   */
  providers: ProviderInfo[];
  /**
   * 是否正在加载。
   */
  loading: boolean;
  /**
   * 当前启停中的 Provider 名称。
   */
  pendingToggleName: string | null;
  /**
   * 当前测试运行中的 Provider 名称。
   */
  pendingTestName: string | null;
  /**
   * 启停回调。
   */
  onToggle: (name: string, enabled: boolean) => void;
  /**
   * 测试运行回调。
   */
  onTestRun: (provider: ProviderInfo) => void;
  /**
   * 编辑回调。
   */
  onEdit: (provider: ProviderInfo) => void;
}

/**
 * Provider 表格。
 */
export function ProviderTable({
  providers,
  loading,
  pendingToggleName,
  pendingTestName,
  onToggle,
  onTestRun,
  onEdit,
}: ProviderTableProps): JSX.Element {
  return (
    <DataTableShell>
      <table className="data-table">
        <thead>
          <tr>
            <th className="w-36">名称</th>
            <th className="w-16">状态</th>
            <th className="w-24 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {loading ? <ProviderTableSkeleton /> : null}
          {providers.map((provider) => {
            const togglePending = pendingToggleName === provider.name;
            const testPending = pendingTestName === provider.name;
            return (
              <tr key={provider.name}>
                <td>
                  <span className="inline-block max-w-36 truncate font-mono font-semibold">{provider.name}</span>
                </td>
                <td>
                  <div className="flex items-center">
                    <Switch
                      checked={provider.enabled}
                      onCheckedChange={(checked) => onToggle(provider.name, checked)}
                      disabled={togglePending}
                    />
                  </div>
                </td>
                <td className="text-right">
                  <div className="flex justify-end gap-1">
                    <TooltipIconButton
                      label="测试运行"
                      variant="ghost"
                      onClick={() => onTestRun(provider)}
                      disabled={testPending || !provider.enabled}
                    >
                      <Play className="h-4 w-4" />
                    </TooltipIconButton>
                    <TooltipIconButton label="编辑" variant="ghost" onClick={() => onEdit(provider)}>
                      <Pencil className="h-4 w-4" />
                    </TooltipIconButton>
                  </div>
                </td>
              </tr>
            );
          })}
          {!loading && !providers.length ? (
            <tr>
              <td colSpan={3}>
                <EmptyState title="暂无执行器" description="系统未加载到任何执行器。" />
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </DataTableShell>
  );
}

/**
 * Provider 表格骨架屏。
 */
function ProviderTableSkeleton(): JSX.Element {
  return (
    <>
      {Array.from({ length: 5 }).map((_, index) => (
        <tr key={index}>
          <td>
            <Skeleton className="h-6 w-24" />
          </td>
          <td>
            <Skeleton className="h-6 w-16" />
          </td>
          <td className="text-right">
            <Skeleton className="ml-auto h-6 w-16" />
          </td>
        </tr>
      ))}
    </>
  );
}
