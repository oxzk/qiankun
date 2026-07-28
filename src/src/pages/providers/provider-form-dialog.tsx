import { useEffect, useState } from "react";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import type { ProviderInfo, ProviderPayload } from "@/types";

export interface ProviderFormDialogProps {
  /**
   * 是否打开弹窗。
   */
  open: boolean;
  /**
   * 当前编辑的 Provider。
   */
  provider: ProviderInfo | null;
  /**
   * 是否正在保存。
   */
  loading: boolean;
  /**
   * 弹窗开关回调。
   */
  onOpenChange: (open: boolean) => void;
  /**
   * 表单提交回调。
   */
  onSubmit: (payload: ProviderPayload) => void;
}

/**
 * Provider 表单弹窗。
 */
export function ProviderFormDialog({
  open,
  provider,
  loading,
  onOpenChange,
  onSubmit,
}: ProviderFormDialogProps): JSX.Element {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [enabled, setEnabled] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    if (!open) return;
    if (provider) {
      setName(provider.name);
      setCode(provider.code);
      setEnabled(provider.enabled);
      return;
    }
    setName("");
    setCode("");
    setEnabled(true);
  }, [open, provider]);

  /**
   * 提交 Provider 表单。
   */
  function handleSubmit(event: React.FormEvent): void {
    event.preventDefault();
    if (!name.trim()) {
      toast({ title: "执行器名称不能为空", variant: "destructive" });
      return;
    }
    if (!code.trim()) {
      toast({ title: "Provider 代码不能为空", variant: "destructive" });
      return;
    }

    onSubmit({
      name: name.trim(),
      code,
      enabled,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{provider ? "编辑执行器" : "新建执行器"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4">
            <Field label="执行器名称" required inline>
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如: template 或 custom-template"
                required
                disabled={Boolean(provider)}
              />
            </Field>
            <div className="grid gap-1.5">
              <div className="grid h-9 grid-cols-[6rem_minmax(0,1fr)] items-center gap-2">
                <span className="field-label whitespace-nowrap">状态</span>
                <Switch checked={enabled} onCheckedChange={setEnabled} className="justify-self-start" />
              </div>
            </div>
          </div>

          <Field label="Provider 代码" required>
            <Textarea
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder={`例如:\nclass TemplateProvider(BaseProvider):\n    name = "template"\n    config_schema = ProviderConfig\n\n    async def execute(self, config):\n        return ProviderResult.ok("执行成功")`}
              rows={16}
              className="font-mono text-xs"
              required
            />
          </Field>

          <div className="mt-4 flex items-center justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" loading={loading}>
              保存
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
