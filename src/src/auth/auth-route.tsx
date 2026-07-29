import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useSession } from "@/auth/session-provider";
import { PageLoading } from "@/components/page-loading";
import { buildLoginPath } from "@/routes";

/**
 * 保护需要登录的业务路由。
 */
export function AuthRoute(): JSX.Element {
  const { ready, loggedIn } = useSession();
  const location = useLocation();

  if (!ready) return <PageLoading />;
  if (!loggedIn) return <Navigate to={buildLoginPath(`${location.pathname}${location.search}`)} replace />;

  return <Outlet />;
}
