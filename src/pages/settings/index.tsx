import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, DatabaseBackup, RotateCcw, User } from "lucide-react";
import { ConfirmDialog, EmptyState, SectionHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { useUrlStringParam } from "@/hooks/use-url-state";
import { backupsApi, notificationsApi } from "@/lib/api";
import { formatByteSize, formatDateTime } from "@/lib/datetime";
import { queryStaleTime } from "@/lib/query-options";
import { queryKeys } from "@/lib/query-keys";
import type { BackupInfo, JsonRecord, NotificationPayload, NotificationSetting, NotifyType } from "@/types";
import { NotificationChannelCard } from "./notification-channel-card";
import { notificationChannelConfigs, type NotificationChannelConfig } from "./notification-config";
import { PasswordSettingsCard } from "./password-settings-card";

interface NotificationSaveVariables {
  /**
   * 通知配置 ID。
   */
  id?: number;
  /**
   * 通知保存参数。
   */
  payload: NotificationPayload;
}

type SettingsTab = "user" | "notify" | "backup";

/**
 * 规范化设置页签。
 */
function resolveSettingsTab(value: string): SettingsTab {
  if (value === "notify" || value === "backup" || value === "user") return value;
  return "user";
}

/**
 * 系统设置页面。
 */
export function SettingsPage(): JSX.Element {
  const [tabParam, setTabParam] = useUrlStringParam("tab", "user");
  const activeTab = resolveSettingsTab(tabParam);
  const [editingChannel, setEditingChannel] = useState<NotifyType | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<BackupInfo | null>(null);
  const [restoreConfirmText, setRestoreConfirmText] = useState("");

  const notificationsQuery = useQuery({
    queryKey: queryKeys.notifications.root,
    queryFn: ({ signal }) => notificationsApi.list({ page: 1, page_size: 100 }, signal),
    enabled: activeTab === "notify",
    staleTime: queryStaleTime.catalog,
  });

  const backupsQuery = useQuery({
    queryKey: queryKeys.backups.root,
    queryFn: ({ signal }) => backupsApi.list(signal),
    enabled: activeTab === "backup",
    staleTime: queryStaleTime.list,
  });

  const saveMutation = useToastMutation<NotificationSetting, NotificationSaveVariables>({
    mutationFn: ({ id, payload }) => {
      if (id !== undefined) return notificationsApi.update(id, payload);
      return notificationsApi.create(payload);
    },
    successTitle: "配置已更新",
    errorTitle: "保存失败",
    invalidate: [queryKeys.notifications.root, queryKeys.notifications.options],
    onSuccess: () => {
      setEditingChannel(null);
    },
  });

  const createBackupMutation = useToastMutation<BackupInfo, void>({
    mutationFn: () => backupsApi.create(),
    successTitle: "备份已创建",
    errorTitle: "备份失败",
    invalidate: [queryKeys.backups.root],
  });

  const restoreBackupMutation = useToastMutation<boolean, BackupInfo>({
    mutationFn: (backup) => backupsApi.restore(backup.filename),
    successTitle: "数据已恢复",
    errorTitle: "恢复失败",
    invalidate: [
      queryKeys.backups.root,
      queryKeys.providers.root,
      queryKeys.tasks.root,
      queryKeys.executions.root,
      queryKeys.notifications.root,
      queryKeys.stats.taskStats,
    ],
    onSuccess: () => {
      setRestoreTarget(null);
      setRestoreConfirmText("");
    },
  });

  const notifications = notificationsQuery.data?.items ?? [];

  /**
   * 按通知类型查找配置。
   */
  function findNotification(type: NotifyType): NotificationSetting | undefined {
    return notifications.find((item) => item.notify_type === type);
  }

  /**
   * 保存通知渠道配置。
   */
  function saveNotificationConfig(
    channelConfig: NotificationChannelConfig,
    item: NotificationSetting | undefined,
    config: JsonRecord,
  ): void {
    saveMutation.mutate({
      id: item?.id,
      payload: {
        name: channelConfig.title,
        notify_type: channelConfig.type,
        enabled: item ? item.enabled : true,
        config,
      },
    });
  }

  const headerLoading =
    (activeTab === "notify" && notificationsQuery.isFetching) ||
    (activeTab === "backup" && backupsQuery.isFetching);

  const restoreFilenameMatched = Boolean(restoreTarget && restoreConfirmText.trim() === restoreTarget.filename);

  return (
    <div className="space-y-6">
      <SectionHeader title="系统设置" description="配置系统报警、数据备份及管理员账户。" loading={headerLoading} />

      <Tabs value={activeTab} onValueChange={setTabParam} className="space-y-4">
        <TabsList>
          <TabsTrigger value="user" className="flex items-center gap-2">
            <User className="h-4 w-4" /> 用户设置
          </TabsTrigger>
          <TabsTrigger value="notify" className="flex items-center gap-2">
            <Bell className="h-4 w-4" /> 通知设置
          </TabsTrigger>
          <TabsTrigger value="backup" className="flex items-center gap-2">
            <DatabaseBackup className="h-4 w-4" /> 数据备份
          </TabsTrigger>
        </TabsList>

        <TabsContent value="user">
          <PasswordSettingsCard />
        </TabsContent>

        <TabsContent value="notify" className="space-y-6">
          <div>
            <h3 className="text-lg font-bold">通知配置</h3>
            <p className="text-sm text-muted-foreground">管理任务执行完成后的通知方式</p>
          </div>

          {notificationsQuery.isLoading ? (
            <NotificationSettingsSkeleton />
          ) : (
            <div className="space-y-6">
              {notificationChannelConfigs.map((channelConfig) => {
                const item = findNotification(channelConfig.type);
                return (
                  <NotificationChannelCard
                    key={channelConfig.type}
                    config={channelConfig}
                    item={item}
                    editing={editingChannel === channelConfig.type}
                    saving={saveMutation.isPending}
                    onEdit={() => setEditingChannel(channelConfig.type)}
                    onCancel={() => setEditingChannel(null)}
                    onSave={(config) => saveNotificationConfig(channelConfig, item, config)}
                  />
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="backup">
          <BackupSettingsPanel
            backups={backupsQuery.data ?? []}
            loading={backupsQuery.isLoading}
            creating={createBackupMutation.isPending}
            restoring={restoreBackupMutation.isPending}
            onCreate={() => createBackupMutation.mutate()}
            onRestore={(backup) => {
              setRestoreConfirmText("");
              setRestoreTarget(backup);
            }}
          />
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={Boolean(restoreTarget)}
        title="恢复数据备份"
        description={`确认恢复备份 "${restoreTarget?.filename ?? ""}"? 当前数据库数据会被备份内容替换。请在下方输入完整文件名以确认。`}
        confirmText="恢复"
        loading={restoreBackupMutation.isPending}
        confirmDisabled={!restoreFilenameMatched}
        onOpenChange={(open) => {
          if (!open) {
            setRestoreTarget(null);
            setRestoreConfirmText("");
          }
        }}
        onConfirm={() => {
          if (restoreTarget && restoreFilenameMatched) restoreBackupMutation.mutate(restoreTarget);
        }}
      >
        <Input
          value={restoreConfirmText}
          onChange={(event) => setRestoreConfirmText(event.target.value)}
          placeholder={restoreTarget?.filename ?? "输入备份文件名"}
          autoComplete="off"
          spellCheck={false}
        />
      </ConfirmDialog>
    </div>
  );
}

interface BackupSettingsPanelProps {
  /**
   * 备份历史。
   */
  backups: BackupInfo[];
  /**
   * 是否正在加载备份历史。
   */
  loading: boolean;
  /**
   * 是否正在创建备份。
   */
  creating: boolean;
  /**
   * 是否正在恢复备份。
   */
  restoring: boolean;
  /**
   * 创建备份回调。
   */
  onCreate: () => void;
  /**
   * 恢复备份回调。
   */
  onRestore: (backup: BackupInfo) => void;
}

/**
 * 数据备份设置面板。
 */
function BackupSettingsPanel({
  backups,
  loading,
  creating,
  restoring,
  onCreate,
  onRestore,
}: BackupSettingsPanelProps): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold">备份历史</h3>
          <p className="text-sm text-muted-foreground">创建数据库快照并按历史备份恢复数据</p>
        </div>
        <Button size="sm" onClick={onCreate} loading={creating}>
          <DatabaseBackup className="mr-1 h-4 w-4" />
          创建备份
        </Button>
      </div>

      {loading ? (
        <BackupListSkeleton />
      ) : backups.length ? (
        <div className="divide-y rounded-lg border bg-card">
          {backups.map((backup) => (
            <div key={backup.filename} className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0 space-y-2">
                <div className="truncate font-mono text-sm font-semibold">{backup.filename}</div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span>{formatDateTime(backup.created_at)}</span>
                  <span>{formatByteSize(backup.size_bytes)}</span>
                  <span>{formatBackupTableCounts(backup.table_counts)}</span>
                </div>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={() => onRestore(backup)} disabled={restoring}>
                <RotateCcw className="mr-1 h-4 w-4" />
                恢复
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border bg-card">
          <EmptyState title="暂无备份" description="创建备份后, 这里会显示可恢复的备份历史。" />
        </div>
      )}
    </div>
  );
}

/**
 * 备份历史骨架屏。
 */
function BackupListSkeleton(): JSX.Element {
  return (
    <div className="divide-y rounded-lg border bg-card">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="flex items-center justify-between p-4">
          <div className="space-y-2">
            <Skeleton className="h-5 w-52" />
            <Skeleton className="h-4 w-80 max-w-full" />
          </div>
          <Skeleton className="h-9 w-20" />
        </div>
      ))}
    </div>
  );
}

/**
 * 格式化备份表记录数。
 */
function formatBackupTableCounts(tableCounts: Record<string, number>): string {
  const total = Object.values(tableCounts).reduce((sum, count) => sum + count, 0);
  return `${Object.keys(tableCounts).length} 张表, ${total} 条记录`;
}

/**
 * 通知设置骨架屏。
 */
function NotificationSettingsSkeleton(): JSX.Element {
  return (
    <div className="space-y-6">
      {notificationChannelConfigs.map((config) => (
        <Card key={config.type}>
          <CardHeader>
            <Skeleton className="mb-2 h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-6 w-96 max-w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
