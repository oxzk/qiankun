import { FormEvent, useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useToastMutation } from "@/hooks/use-toast-mutation";
import { authApi } from "@/lib/api";
import { storage } from "@/lib/storage";
import type { TokenResponse } from "@/types";

export interface LoginPageProps {
  /**
   * 登录成功后的回调。
   */
  onLogin: () => void;
}

/**
 * 管理员登录页面。
 * 苹果极简左右分栏, 两侧风格反差, 不复用业务区组件样式体系。
 */
export function LoginPage({ onLogin }: LoginPageProps): JSX.Element {
  const formId = useId();
  const usernameId = `${formId}-username`;
  const passwordId = `${formId}-password`;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const loginMutation = useToastMutation<TokenResponse, { username: string; password: string }>({
    mutationFn: ({ username: loginUsername, password: loginPassword }) =>
      authApi.login(loginUsername.trim(), loginPassword),
    successTitle: "登录成功",
    errorTitle: "登录失败",
    onSuccess: (token) => {
      storage.setToken(token.access_token);
      onLogin();
    },
  });

  /**
   * 提交登录表单。
   */
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    loginMutation.mutate({ username, password });
  }

  /**
   * 切换密码明文可见性。
   */
  function togglePasswordVisibility(): void {
    setShowPassword((value) => !value);
  }

  const isPending = loginMutation.isPending;

  return (
    <main className="login-apple">
      <section className="login-apple__brand" aria-label="产品介绍">
        <div className="login-apple__brand-glow" aria-hidden="true" />
        <div className="login-apple__brand-inner">
          <p className="login-apple__brand-kicker">Control Console</p>
          <h1 className="login-apple__brand-title">
            QianKun
            <span>任务编排</span>
          </h1>
          <p className="login-apple__brand-desc">统一调度 · 清晰链路 · 可靠执行</p>
          <ul className="login-apple__brand-points">
            <li>任务管理</li>
            <li>执行记录</li>
            <li>执行器接入</li>
          </ul>
        </div>
      </section>

      <section className="login-apple__auth" aria-label="登录">
        <div className="login-apple__auth-inner">
          <header className="login-apple__header">
            <div className="login-apple__mark" aria-hidden="true">
              <span className="login-apple__mark-glow" />
              <div className="login-apple__mark-icon">
                <img src="/logo.svg" alt="" className="login-apple__logo" />
              </div>
            </div>
            <div className="login-apple__heading">
              <h2 className="login-apple__title">登录 QianKun</h2>
              <div className="login-apple__rule" />
            </div>
          </header>

          <form className="login-apple__form" onSubmit={submit} noValidate>
            <div className="login-apple__field">
              <label className="login-apple__label" htmlFor={usernameId}>
                用户名
              </label>
              <input
                id={usernameId}
                className="login-apple__input"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
                spellCheck={false}
                disabled={isPending}
              />
            </div>

            <div className="login-apple__field">
              <label className="login-apple__label" htmlFor={passwordId}>
                密码
              </label>
              <div className="login-apple__password">
                <input
                  id={passwordId}
                  className="login-apple__input login-apple__input--password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  disabled={isPending}
                />
                <button
                  type="button"
                  className="login-apple__eye"
                  onClick={togglePasswordVisibility}
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                  disabled={isPending}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button type="submit" className="login-apple__submit" disabled={isPending} aria-busy={isPending || undefined}>
              {isPending ? "正在登录…" : "继续"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
