import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useSession } from "@/auth/session-provider";
import { buildLoginPath } from "@/routes";

/**
 * 保护需要登录的业务路由。
 */
export function AuthRoute(): JSX.Element {
  const { loggedIn } = useSession();
  const location = useLocation();

  if (!loggedIn) return <Navigate to={buildLoginPath(`${location.pathname}${location.search}`)} replace />;

  return <Outlet />;
}
