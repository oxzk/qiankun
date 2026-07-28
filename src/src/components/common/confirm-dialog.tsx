import { Button, type ButtonProps } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export interface ConfirmDialogProps {
  /**
   * 是否显示确认弹窗。
   */
  open: boolean;
  /**
   * 弹窗标题。
   */
  title: string;
  /**
   * 弹窗说明。
   */
  description: string;
  /**
   * 确认按钮文本。
   */
  confirmText?: string;
  /**
   * 确认按钮样式。
   */
  confirmVariant?: ButtonProps["variant"];
  /**
   * 是否处于提交中。
   */
  loading?: boolean;
  /**
   * 弹窗开关回调。
   */
  onOpenChange: (open: boolean) => void;
  /**
   * 确认回调。
   */
  onConfirm: () => void;
}

/**
 * 破坏性或高影响操作确认弹窗。
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = "确认",
  confirmVariant = "destructive",
  loading = false,
  onOpenChange,
  onConfirm,
}: ConfirmDialogProps): JSX.Element {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{description}</p>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button type="button" variant={confirmVariant} loading={loading} onClick={onConfirm}>
            {confirmText}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
