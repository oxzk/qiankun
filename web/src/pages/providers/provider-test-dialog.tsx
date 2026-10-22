import { FormEvent, useEffect, useState } from "react";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { formatJson, parseJsonObject } from "@/lib/json-schema";
import type { JsonRecord, ProviderInfo } from "@/types";

export interface ProviderTestDialogProps {
  /**
   * 是否打开弹窗。
   */
  open: boolean;
  /**
   * 当前测试的 Provider。
   */
  provider: ProviderInfo | null;
  /**
   * 是否正在测试运行。
   */
  loading: boolean;
  /**
   * 弹窗开关回调。
   */
  onOpenChange: (open: boolean) => void;
  /**
   * 测试提交回调。
   */
  onSubmit: (provider: ProviderInfo, config: JsonRecord) => void;
}

/**
 * Provider 测试运行弹窗。
 */
export function ProviderTestDialog({
  open,
  provider,
  loading,
  onOpenChange,
  onSubmit,
}: ProviderTestDialogProps): JSX.Element {
  const [configText, setConfigText] = useState(formatJson({}));
  const { toast } = useToast();

  useEffect(() => {
    if (open) setConfigText(formatJson({}));
  }, [open, provider]);

  /**
   * 提交测试运行配置。
   */
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!provider) return;

    let config: JsonRecord;
    try {
      config = parseJsonObject(configText);
    } catch (error) {
      toast({
        title: "JSON 格式错误",
        description: error instanceof Error ? error.message : "请输入有效的 JSON 对象格式。",
        variant: "destructive",
      });
      return;
    }

    onSubmit(provider, config);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>测试运行 {provider?.name ?? ""}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={submit}
          className="flex min-h-0 flex-1 flex-col overflow-hidden"
        >
          <DialogBody className="space-y-4">
            <Field label="配置参数 (JSON)">
              <Textarea
                value={configText}
                onChange={(event) => setConfigText(event.target.value)}
                placeholder={`例如:\n{\n  "message": "hello"\n}`}
                rows={10}
                className="font-mono text-xs"
              />
            </Field>
          </DialogBody>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" loading={loading} disabled={!provider}>
              运行测试
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
