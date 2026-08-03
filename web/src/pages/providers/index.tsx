import { useCallback, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw } from "lucide-react";
import { EmptyState, PaginationBar, SectionHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { useTableParams } from "@/hooks/use-table-params";
import { useToast } from "@/hooks/use-toast";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { getErrorMessage, providersApi } from "@/lib/api";
import { queryStaleTime } from "@/lib/query-options";
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
  const { page, setPage } = useTableParams({
    defaultFilters: {},
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderInfo | null>(null);
  const [testingProvider, setTestingProvider] = useState<ProviderInfo | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const query = useQuery({
    queryKey: queryKeys.providers.list({ page }),
    queryFn: ({ signal }) => providersApi.list({ page, page_size: 20 }, signal),
    staleTime: queryStaleTime.catalog,
    placeholderData: keepPreviousData,
  });

  const saveMutation = useToastMutation<ProviderInfo, ProviderPayload>({
    mutationFn: (payload) => {
      if (editingProvider) return providersApi.update(editingProvider.name, payload);
      return providersApi.create(payload);
    },
    successTitle: () => (editingProvider ? "执行器已更新" : "执行器已创建"),
    errorTitle: "保存失败",
    invalidate: [queryKeys.providers.root, queryKeys.providers.options, queryKeys.tasks.root],
    onSuccess: () => {
      setDialogOpen(false);
    },
  });

  // 开关启停操作的乐观更新
  const toggleMutation = useMutation({
    mutationFn: ({ name, enabled }: ProviderToggleVariables) =>
      enabled ? providersApi.enable(name) : providersApi.disable(name),
    onMutate: async ({ name, enabled }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.providers.root });
      const previousQueries = queryClient.getQueriesData({ queryKey: queryKeys.providers.root });

      queryClient.setQueriesData({ queryKey: queryKeys.providers.root }, (old: unknown) => {
        if (!old || typeof old !== "object" || !("items" in old) || !Array.isArray((old as { items: ProviderInfo[] }).items)) {
          return old;
        }
        return {
          ...old,
          items: (old as { items: ProviderInfo[] }).items.map((item) =>
            item.name === name ? { ...item, enabled } : item,
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
      toast({ title: variables.enabled ? "执行器已启用" : "执行器已停用" });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.providers.root });
      void queryClient.invalidateQueries({ queryKey: queryKeys.providers.options });
      void queryClient.invalidateQueries({ queryKey: queryKeys.tasks.root });
    },
  });

  const syncMutation = useToastMutation<boolean, void>({
    mutationFn: () => providersApi.sync(),
    successTitle: "执行器已同步",
    errorTitle: "同步失败",
    invalidate: [queryKeys.providers.root, queryKeys.providers.options, queryKeys.tasks.root],
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

  const openEdit = useCallback((provider: ProviderInfo) => {
    setEditingProvider(provider);
    setDialogOpen(true);
  }, []);

  const handleToggle = useCallback(
    (name: string, enabled: boolean) => {
      toggleMutation.mutate({ name, enabled });
    },
    [toggleMutation],
  );

  const handleTestRun = useCallback((provider: ProviderInfo) => {
    setTestingProvider(provider);
  }, []);

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
        onRefresh={() => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.providers.root });
        }}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={() => syncMutation.mutate()} loading={syncMutation.isPending}>
              <RefreshCw className="mr-1 h-4 w-4" />
              同步执行器
            </Button>
            <Button size="sm" onClick={openCreate}>
              <Plus className="mr-1 h-4 w-4" />
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
        onToggle={handleToggle}
        onTestRun={handleTestRun}
        onEdit={openEdit}
      />

      <PaginationBar
        page={query.data?.page ?? page}
        pageSize={query.data?.page_size}
        total={query.data?.total}
        onChange={setPage}
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
