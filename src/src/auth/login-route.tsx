import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "@/auth/session-provider";
import { PageLoading } from "@/components/page-loading";
import { LoginPage } from "@/pages/login";
import { sanitizeRedirectPath } from "@/routes";
import type { TokenResponse } from "@/types";

/**
 * 登录路由容器。
 */
export function LoginRoute(): JSX.Element {
  const { ready, loggedIn, completeLogin } = useSession();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const redirect = sanitizeRedirectPath(params.get("redirect"));

  if (!ready) return <PageLoading />;
  if (loggedIn) return <Navigate to={redirect} replace />;

  /**
   * 登录成功后写入会话并跳转。
   */
  function handleLogin(token: TokenResponse): void {
    completeLogin(token);
    navigate(redirect, { replace: true });
  }

  return <LoginPage onLogin={handleLogin} />;
}
