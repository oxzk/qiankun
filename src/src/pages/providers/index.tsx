import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Plus, RefreshCw } from "lucide-react";
import { EmptyState, SectionHeader } from "@/components/common";
import { PaginationBar } from "@/components/data/pagination-bar";
import { Button } from "@/components/ui/button";
import { usePagination } from "@/hooks/use-pagination";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { getErrorMessage, providersApi } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { JsonRecord, ProviderInfo, ProviderPayload, ProviderResult } from "@/types";
import { ProviderFormDialog } from "./provider-form-dialog";
import { ProviderTable } from "./provider-table";
import { ProviderTestDialog } from "./provider-test-dialog";

interface ProviderToggleVariables {
  /**
   * Provider 名称。
   */
  name: string;
  /**
   * 是否启用。
   */
  enabled: boolean;
}

interface ProviderTestRunVariables {
  /**
   * Provider 名称。
   */
  name: string;
  /**
   * 测试运行配置。
   */
  config: JsonRecord;
}

/**
 * 执行器管理页面。
 */
export function ProvidersPage(): JSX.Element {
  const { page, setPage } = usePagination();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderInfo | null>(null);
  const [testingProvider, setTestingProvider] = useState<ProviderInfo | null>(null);

  const query = useQuery({
    queryKey: queryKeys.providers.list({ page }),
    queryFn: () => providersApi.list({ page, page_size: 20 }),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

  const saveMutation = useToastMutation<ProviderInfo, ProviderPayload>({
    mutationFn: (payload) => {
      if (editingProvider) return providersApi.update(editingProvider.name, payload);
      return providersApi.create(payload);
    },
    successTitle: () => (editingProvider ? "执行器已更新" : "执行器已创建"),
    errorTitle: "保存失败",
    invalidate: [queryKeys.providers.root, queryKeys.tasks.root],
    onSuccess: () => {
      setDialogOpen(false);
    },
  });

  const toggleMutation = useToastMutation<ProviderInfo, ProviderToggleVariables>({
    mutationFn: ({ name, enabled }) => (enabled ? providersApi.enable(name) : providersApi.disable(name)),
    successTitle: "执行器状态已更新",
    errorTitle: "操作失败",
    invalidate: [queryKeys.providers.root, queryKeys.tasks.root],
  });

  const syncMutation = useToastMutation<boolean, void>({
    mutationFn: () => providersApi.sync(),
    successTitle: "执行器已同步",
    errorTitle: "同步失败",
    invalidate: [queryKeys.providers.root, queryKeys.tasks.root],
  });

  const testRunMutation = useToastMutation<ProviderResult, ProviderTestRunVariables>({
    mutationFn: ({ name, config }) => providersApi.testRun(name, config),
    successToast: (result) => ({
      title: result.success ? "测试运行成功" : "测试运行失败",
      description: result.message || undefined,
      variant: result.success ? undefined : "destructive",
    }),
    errorTitle: "测试运行失败",
    onSuccess: () => {
      setTestingProvider(null);
    },
  });

  /**
   * 打开创建弹窗。
   */
  function openCreate(): void {
    setEditingProvider(null);
    setDialogOpen(true);
  }

  /**
   * 打开编辑弹窗。
   */
  function openEdit(provider: ProviderInfo): void {
    setEditingProvider(provider);
    setDialogOpen(true);
  }

  const providers = query.data?.items ?? [];
  const pendingToggleName =
    toggleMutation.isPending && toggleMutation.variables ? toggleMutation.variables.name : null;
  const pendingTestName =
    testRunMutation.isPending && testRunMutation.variables ? testRunMutation.variables.name : null;

  return (
    <div className="space-y-4">
      <SectionHeader
        title="执行器管理"
        description="管理和配置系统内置与自定义执行器 (Providers)。您可以新建、编辑或启停执行器。"
        loading={query.isFetching || syncMutation.isPending}
        onRefresh={() => void query.refetch()}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={() => syncMutation.mutate()} loading={syncMutation.isPending}>
              <RefreshCw className="h-4 w-4 mr-1" />
              同步执行器
            </Button>
            <Button size="sm" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-1" />
              新建执行器
            </Button>
          </>
        }
      />

      {query.error ? <EmptyState title="执行器加载失败" description={getErrorMessage(query.error)} /> : null}

      <ProviderTable
        providers={providers}
        loading={query.isLoading}
        pendingToggleName={pendingToggleName}
        pendingTestName={pendingTestName}
        onToggle={(name, enabled) => toggleMutation.mutate({ name, enabled })}
        onTestRun={(provider) => setTestingProvider(provider)}
        onEdit={openEdit}
      />

      <PaginationBar
        page={query.data?.page ?? page}
        pageSize={query.data?.page_size}
        total={query.data?.total}
        onPageChange={setPage}
      />

      <ProviderFormDialog
        open={dialogOpen}
        provider={editingProvider}
        loading={saveMutation.isPending}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) setEditingProvider(null);
        }}
        onSubmit={(payload) => saveMutation.mutate(payload)}
      />

      <ProviderTestDialog
        open={Boolean(testingProvider)}
        provider={testingProvider}
        loading={testRunMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setTestingProvider(null);
        }}
        onSubmit={(provider, config) => testRunMutation.mutate({ name: provider.name, config })}
      />
    </div>
  );
}
