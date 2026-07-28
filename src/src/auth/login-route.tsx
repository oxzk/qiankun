import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "@/auth/session-provider";
import { LoginPage } from "@/pages/login";
import { sanitizeRedirectPath } from "@/routes";

/**
 * 登录路由容器。
 */
export function LoginRoute(): JSX.Element {
  const { loggedIn, completeLogin } = useSession();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const redirect = sanitizeRedirectPath(params.get("redirect"));

  if (loggedIn) return <Navigate to={redirect} replace />;

  return (
    <LoginPage
      onLogin={() => {
        completeLogin();
        navigate(redirect, { replace: true });
      }}
    />
  );
}
