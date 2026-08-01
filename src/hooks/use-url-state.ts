import { useCallback, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * 管理 URL 字符串查询参数。
 */
export function useUrlStringParam(name: string, defaultValue = ""): readonly [string, (value: string) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const value = searchParams.get(name) ?? defaultValue;

  const setValue = useCallback(
    (nextValue: string) => {
      setSearchParams(
        (current) => {
          const nextParams = new URLSearchParams(current);
          if (!nextValue || nextValue === defaultValue) {
            nextParams.delete(name);
          } else {
            nextParams.set(name, nextValue);
          }
          return nextParams;
        },
        { replace: true },
      );
    },
    [defaultValue, name, setSearchParams],
  );

  return [value, setValue] as const;
}

/**
 * 批量更新 URL 查询参数。
 */
export function useUrlParamsWriter(): (updates: Record<string, string | null | undefined>) => void {
  const [, setSearchParams] = useSearchParams();

  return useCallback(
    (updates: Record<string, string | null | undefined>) => {
      setSearchParams(
        (current) => {
          const nextParams = new URLSearchParams(current);
          Object.entries(updates).forEach(([key, value]) => {
            if (value === null || value === undefined || value === "") {
              nextParams.delete(key);
            } else {
              nextParams.set(key, value);
            }
          });
          return nextParams;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );
}

/**
 * 管理 URL 分页页码, 并在筛选依赖变化时回到第一页。
 */
export function usePagination(resetDeps: readonly unknown[] = []): {
  page: number;
  setPage: (page: number | ((page: number) => number)) => void;
} {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawPage = searchParams.get("page");
  const parsed = Number.parseInt(rawPage || "1", 10);
  const page = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  const depsKey = JSON.stringify(resetDeps);
  const prevDepsKeyRef = useRef(depsKey);

  const setPage = useCallback(
    (next: number | ((current: number) => number)) => {
      setSearchParams(
        (current) => {
          const currentPage = Math.max(1, Number.parseInt(current.get("page") || "1", 10) || 1);
          const resolved = typeof next === "function" ? next(currentPage) : next;
          const nextParams = new URLSearchParams(current);
          if (!resolved || resolved <= 1) {
            nextParams.delete("page");
          } else {
            nextParams.set("page", String(resolved));
          }
          return nextParams;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  useEffect(() => {
    if (prevDepsKeyRef.current === depsKey) return;
    prevDepsKeyRef.current = depsKey;
    setSearchParams(
      (current) => {
        if (!current.get("page")) return current;
        const nextParams = new URLSearchParams(current);
        nextParams.delete("page");
        return nextParams;
      },
      { replace: true },
    );
  }, [depsKey, setSearchParams]);

  return { page, setPage };
}
