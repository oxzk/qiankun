import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, type Resolver } from "react-hook-form";
import { Field } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { authApi } from "@/lib/api";
import { passwordFormSchema, type PasswordFormValues } from "@/lib/forms";

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
  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordFormSchema) as Resolver<PasswordFormValues>,
    defaultValues: {
      oldPassword: "",
      newPassword: "",
      confirmPassword: "",
    },
  });

  const passwordMutation = useToastMutation<boolean, PasswordChangeVariables>({
    mutationFn: ({ oldPassword: currentPassword, newPassword: nextPassword }) =>
      authApi.changePassword(currentPassword, nextPassword),
    successTitle: "密码修改成功，请妥善保管新密码",
    errorTitle: "密码修改失败",
    onSuccess: () => {
      form.reset();
    },
  });

  /**
   * 修改管理员密码。
   */
  function handlePasswordChange(values: PasswordFormValues): void {
    passwordMutation.mutate({
      oldPassword: values.oldPassword,
      newPassword: values.newPassword,
    });
  }

  return (
    <Card className="max-w-md">
      <CardHeader>
        <CardTitle>修改密码</CardTitle>
        <CardDescription>更新系统默认管理员 (admin) 的登录密码以保证账户安全。</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(handlePasswordChange)} className="space-y-4">
          <Field
            label="旧密码"
            required
            error={Boolean(form.formState.errors.oldPassword)}
            errorMessage={form.formState.errors.oldPassword?.message}
          >
            <Input
              type="password"
              {...form.register("oldPassword")}
              placeholder="输入当前旧密码"
              autoComplete="current-password"
              required
            />
          </Field>
          <Field
            label="新密码"
            required
            error={Boolean(form.formState.errors.newPassword)}
            errorMessage={form.formState.errors.newPassword?.message}
          >
            <Input
              type="password"
              {...form.register("newPassword")}
              placeholder="输入新密码"
              autoComplete="new-password"
              required
            />
          </Field>
          <Field
            label="确认新密码"
            required
            error={Boolean(form.formState.errors.confirmPassword)}
            errorMessage={form.formState.errors.confirmPassword?.message}
          >
            <Input
              type="password"
              {...form.register("confirmPassword")}
              placeholder="再次输入新密码"
              autoComplete="new-password"
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
