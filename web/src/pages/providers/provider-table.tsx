import { memo } from "react";
import { Pencil, Play } from "lucide-react";
import { DataTableShell, EmptyState, TableSkeleton, TooltipIconButton } from "@/components/common";
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

interface ProviderRowProps {
  /**
   * Provider 数据。
   */
  provider: ProviderInfo;
  /**
   * 启停是否进行中。
   */
  togglePending: boolean;
  /**
   * 测试是否进行中。
   */
  testPending: boolean;
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

const PROVIDER_SKELETON_COLUMNS = [
  { widthClass: "w-24" },
  { widthClass: "w-16" },
  { widthClass: "w-16", align: "right" as const },
];

/**
 * Provider 行。
 */
const ProviderRow = memo(function ProviderRow({
  provider,
  togglePending,
  testPending,
  onToggle,
  onTestRun,
  onEdit,
}: ProviderRowProps): JSX.Element {
  return (
    <tr>
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
});

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
          {loading ? <TableSkeleton columns={PROVIDER_SKELETON_COLUMNS} rows={5} /> : null}
          {providers.map((provider) => (
            <ProviderRow
              key={provider.name}
              provider={provider}
              togglePending={pendingToggleName === provider.name}
              testPending={pendingTestName === provider.name}
              onToggle={onToggle}
              onTestRun={onTestRun}
              onEdit={onEdit}
            />
          ))}
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
