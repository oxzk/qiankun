import { useState } from "react";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { authApi } from "@/lib/api";

interface PasswordChangeVariables {
  /**
   * 旧密码。
   */
  oldPassword: string;
  /**
   * 新密码。
   */
  newPassword: string;
}

/**
 * 密码设置卡片。
 */
export function PasswordSettingsCard(): JSX.Element {
  const { toast } = useToast();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const passwordMutation = useToastMutation<boolean, PasswordChangeVariables>({
    mutationFn: ({ oldPassword: currentPassword, newPassword: nextPassword }) =>
      authApi.changePassword(currentPassword, nextPassword),
    successTitle: "密码修改成功，请妥善保管新密码",
    errorTitle: "密码修改失败",
    onSuccess: () => {
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
  });

  /**
   * 修改管理员密码。
   */
  function handlePasswordChange(event: React.FormEvent): void {
    event.preventDefault();
    if (!oldPassword) {
      toast({ title: "请输入旧密码", variant: "destructive" });
      return;
    }
    if (!newPassword) {
      toast({ title: "请输入新密码", variant: "destructive" });
      return;
    }
    if (newPassword !== confirmPassword) {
      toast({ title: "两次输入的密码不一致", variant: "destructive" });
      return;
    }
    passwordMutation.mutate({ oldPassword, newPassword });
  }

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle>修改密码</CardTitle>
        <CardDescription>更新系统默认管理员 (admin) 的登录密码以保证账户安全。</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handlePasswordChange} className="space-y-4">
          <Field label="旧密码" required>
            <Input
              type="password"
              value={oldPassword}
              onChange={(event) => setOldPassword(event.target.value)}
              placeholder="输入当前旧密码"
              autoComplete="off"
              required
            />
          </Field>
          <Field label="新密码" required>
            <Input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder="输入新密码"
              autoComplete="off"
              required
            />
          </Field>
          <Field label="确认新密码" required>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="再次输入新密码"
              autoComplete="off"
              required
            />
          </Field>
          <Button type="submit" loading={passwordMutation.isPending} className="w-full">
            保存新密码
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
