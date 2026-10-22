import { useEffect, useState } from "react";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import type { JsonRecord, NotificationSetting } from "@/types";
import type { NotificationChannelConfig } from "./notification-config";

export interface NotificationChannelCardProps {
  /**
   * 渠道配置。
   */
  config: NotificationChannelConfig;
  /**
   * 已保存的通知配置。
   */
  item?: NotificationSetting;
  /**
   * 是否正在编辑。
   */
  editing: boolean;
  /**
   * 是否正在保存。
   */
  saving: boolean;
  /**
   * 编辑回调。
   */
  onEdit: () => void;
  /**
   * 取消编辑回调。
   */
  onCancel: () => void;
  /**
   * 保存回调。
   */
  onSave: (config: JsonRecord) => void;
}

/**
 * 通知渠道配置卡片。
 */
export function NotificationChannelCard({
  config,
  item,
  editing,
  saving,
  onEdit,
  onCancel,
  onSave,
}: NotificationChannelCardProps): JSX.Element {
  const [values, setValues] = useState<Record<string, string>>({});
  const { toast } = useToast();

  useEffect(() => {
    if (!editing) return;
    setValues(
      Object.fromEntries(
        config.fields.map((field) => [field.key, String(item?.config[field.key] ?? "")]),
      ),
    );
  }, [config.fields, editing, item]);

  /**
   * 更新字段值。
   */
  function updateValue(key: string, value: string): void {
    setValues((current) => ({ ...current, [key]: value }));
  }

  /**
   * 保存渠道配置。
   */
  function handleSubmit(event: React.FormEvent): void {
    event.preventDefault();
    const missingField = config.fields.find((field) => !values[field.key]?.trim());
    if (missingField) {
      toast({ title: `${missingField.label} 不能为空`, variant: "destructive" });
      return;
    }
    onSave(Object.fromEntries(config.fields.map((field) => [field.key, values[field.key].trim()])));
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <div className="space-y-1">
          <CardTitle className="text-base font-semibold">{config.title}</CardTitle>
          <CardDescription>{config.description}</CardDescription>
        </div>
        {!editing ? (
          <Button type="button" variant="outline" size="sm" onClick={onEdit}>
            编辑
          </Button>
        ) : null}
      </CardHeader>
      <CardContent>
        {editing ? (
          <form onSubmit={handleSubmit} className="space-y-4 pt-2">
            {config.fields.map((field) => (
              <Field key={field.key} label={field.label} required>
                <Input
                  type={field.type ?? "text"}
                  value={values[field.key] ?? ""}
                  onChange={(event) => updateValue(field.key, event.target.value)}
                  placeholder={field.placeholder}
                  required
                />
              </Field>
            ))}
            <div className="flex items-center justify-end gap-2">
              <Button size="sm" type="submit" loading={saving}>
                保存
              </Button>
              <Button variant="outline" size="sm" type="button" onClick={onCancel}>
                取消
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-2 pt-2 text-sm text-muted-foreground">
            {config.fields.map((field) => (
              <div key={field.key}>
                {field.label}: {item?.config[field.key] ? (
                  <span className="ml-1 font-mono text-foreground">
                    {field.masked ? "••••••••" : String(item.config[field.key])}
                  </span>
                ) : (
                  <span className="ml-1 font-medium text-destructive">未配置</span>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
