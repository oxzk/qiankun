import { lazy, type ComponentType, type LazyExoticComponent } from "react";
import { Cpu, Gauge, History, Settings, Timer, type LucideIcon } from "lucide-react";
import { Navigate, type Location } from "react-router-dom";

export const ROOT_PATH = "/dashboard";
export const LOGIN_PATH = "/login";

/**
 * 懒加载页面组件并映射命名导出。
 */
function lazyPage<T extends Record<string, ComponentType>>(
  loader: () => Promise<T>,
  exportName: keyof T,
): LazyExoticComponent<ComponentType> {
  return lazy(async () => {
    const module = await loader();
    return { default: module[exportName] as ComponentType };
  });
}

const DashboardPage = lazyPage(() => import("@/pages/dashboard"), "DashboardPage");
const TasksPage = lazyPage(() => import("@/pages/tasks"), "TasksPage");
const ExecutionsPage = lazyPage(() => import("@/pages/executions"), "ExecutionsPage");
const ProvidersPage = lazyPage(() => import("@/pages/providers"), "ProvidersPage");
const SettingsPage = lazyPage(() => import("@/pages/settings"), "SettingsPage");

export interface MenuRoute {
  /**
   * 菜单唯一标识。
   */
  key: "dashboard" | "tasks" | "executions" | "providers" | "settings";
  /**
   * 菜单展示名称。
   */
  label: string;
  /**
   * 路由路径。
   */
  path: string;
  /**
   * 菜单图标。
   */
  icon: LucideIcon;
  /**
   * 路由页面元素。
   */
  element: JSX.Element;
}

export const menuRoutes: MenuRoute[] = [
  { key: "dashboard", label: "概览", path: "/dashboard", icon: Gauge, element: <DashboardPage /> },
  { key: "tasks", label: "任务管理", path: "/tasks", icon: Timer, element: <TasksPage /> },
  { key: "executions", label: "执行记录", path: "/executions", icon: History, element: <ExecutionsPage /> },
  { key: "providers", label: "执行器管理", path: "/providers", icon: Cpu, element: <ProvidersPage /> },
  { key: "settings", label: "系统设置", path: "/settings", icon: Settings, element: <SettingsPage /> },
];

/**
 * 根路径重定向。
 */
export function RootRedirect(): JSX.Element {
  return <Navigate to={ROOT_PATH} replace />;
}

/**
 * 判断是否登录路径。
 */
export function isLoginPath(pathname: string): boolean {
  return pathname === LOGIN_PATH;
}

/**
 * 构建登录跳转路径。
 */
export function buildLoginPath(redirect: string): string {
  return `${LOGIN_PATH}?redirect=${encodeURIComponent(sanitizeRedirectPath(redirect))}`;
}

/**
 * 规范化登录后的站内跳转路径。
 */
export function sanitizeRedirectPath(redirect: string | null | undefined): string {
  if (!redirect) return ROOT_PATH;
  if (!redirect.startsWith("/") || redirect.startsWith("//")) return ROOT_PATH;
  if (hasControlChars(redirect)) return ROOT_PATH;
  if (redirect === LOGIN_PATH) return ROOT_PATH;
  return redirect;
}

/**
 * 判断路径是否包含控制字符。
 */
function hasControlChars(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

/**
 * 读取受保护页面路径。
 */
export function readProtectedPath(location: Location): string {
  return `${location.pathname}${location.search}`;
}

/**
 * 将绝对路径转换为嵌套路由路径。
 */
export function toNestedRoutePath(path: string): string {
  return path.replace(/^\//, "");
}

/**
 * 匹配当前菜单路由。
 */
export function resolveMenuRoute(pathname: string): MenuRoute | undefined {
  return menuRoutes.find((route) => pathname === route.path || pathname.startsWith(`${route.path}/`));
}
