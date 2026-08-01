import { Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthRoute } from "@/auth/auth-route";
import { LoginRoute } from "@/auth/login-route";
import { SessionProvider } from "@/auth/session-provider";
import { ErrorBoundary } from "@/components/error-boundary";
import { Layout } from "@/components/layouts";
import { PageLoading } from "@/components/page-loading";
import { NotFound } from "@/pages/not-found";
import { LOGIN_PATH, menuRoutes, RootRedirect, toNestedRoutePath } from "@/routes";

/**
 * QianKun 前端主应用。
 */
export default function App(): JSX.Element {
  return (
    <BrowserRouter>
      <SessionProvider>
        <ErrorBoundary>
          <Layout>
            <Suspense fallback={<PageLoading />}>
              <Routes>
                <Route path={LOGIN_PATH} element={<LoginRoute />} />
                <Route path="/" element={<AuthRoute />}>
                  <Route index element={<RootRedirect />} />
                  {menuRoutes.map((route) => (
                    <Route key={route.key} path={toNestedRoutePath(route.path)} element={route.element} />
                  ))}
                  <Route path="*" element={<NotFound />} />
                </Route>
              </Routes>
            </Suspense>
          </Layout>
        </ErrorBoundary>
      </SessionProvider>
    </BrowserRouter>
  );
}
