import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Header } from "@/components/layouts/header";
import { storage } from "@/lib/storage";
import { isLoginPath } from "@/routes";

export interface LayoutProps {
  /**
   * 业务页面内容。
   */
  children: ReactNode;
}

/**
 * 全局页面布局。
 */
export function Layout({ children }: LayoutProps): JSX.Element {
  const [dark, setDark] = useState(() => storage.getTheme() === "dark");
  const location = useLocation();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    storage.setTheme(dark ? "dark" : "light");
  }, [dark]);

  if (isLoginPath(location.pathname)) return <>{children}</>;

  return (
    <>
      <Header dark={dark} onToggleTheme={() => setDark((value) => !value)} />
      <main className="mx-auto max-w-[1400px] px-4 py-6 md:px-8 md:py-8">{children}</main>
    </>
  );
}
