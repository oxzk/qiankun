import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

export interface UseTableParamsOptions<T extends Record<string, string | number | boolean | null | undefined>> {
  /**
   * 默认筛选参数。
   */
  defaultFilters: T;
  /**
   * 需要防抖的筛选字段名。
   */
  debounceKeys?: (keyof T)[];
  /**
   * 防抖延迟 (毫秒), 默认 300ms。
   */
  debounceDelay?: number;
  /**
   * 每页条数参数名, 默认 "page_size"。
   */
  pageSizeKey?: string;
  /**
   * 默认每页条数, 默认 20。
   */
  defaultPageSize?: number;
}

export interface UseTableParamsResult<T extends Record<string, string | number | boolean | null | undefined>> {
  /**
   * 当前筛选参数 (即时输入值)。
   */
  filters: T;
  /**
   * 经过防抖后的筛选参数 (用于 API 请求)。
   */
  debouncedFilters: T;
  /**
   * 当前页码。
   */
  page: number;
  /**
   * 每页条数。
   */
  pageSize: number;
  /**
   * 设置单项筛选参数。
   */
  setFilter: <K extends keyof T>(key: K, value: T[K]) => void;
  /**
   * 批量设置筛选参数。
   */
  setFilters: (updates: Partial<T>) => void;
  /**
   * 重置所有筛选参数到默认值并返回第一页。
   */
  resetFilters: () => void;
  /**
   * 修改页码。
   */
  setPage: (page: number | ((current: number) => number)) => void;
  /**
   * 修改每页条数。
   */
  setPageSize: (pageSize: number) => void;
}

/**
 * 通用表格参数管理 Hook (涵盖 URL 双向同步、输入防抖、分页联动与一键重置)。
 */
export function useTableParams<T extends Record<string, string | number | boolean | null | undefined>>({
  defaultFilters,
  debounceKeys = [],
  debounceDelay = 300,
  pageSizeKey = "page_size",
  defaultPageSize = 20,
}: UseTableParamsOptions<T>): UseTableParamsResult<T> {
  const [searchParams, setSearchParams] = useSearchParams();

  // 从 URL 初始化 filters
  const filtersFromUrl = useMemo(() => {
    const result = { ...defaultFilters };
    (Object.keys(defaultFilters) as (keyof T)[]).forEach((key) => {
      const urlValue = searchParams.get(String(key));
      if (urlValue !== null) {
        const defaultValue = defaultFilters[key];
        if (typeof defaultValue === "boolean") {
          result[key] = (urlValue === "true" ? true : urlValue === "false" ? false : defaultValue) as T[keyof T];
        } else if (typeof defaultValue === "number") {
          const parsedNum = Number(urlValue);
          result[key] = (Number.isFinite(parsedNum) ? parsedNum : defaultValue) as T[keyof T];
        } else {
          result[key] = urlValue as T[keyof T];
        }
      }
    });
    return result;
  }, [defaultFilters, searchParams]);

  // 从 URL 读取 page
  const page = useMemo(() => {
    const raw = searchParams.get("page");
    const parsed = Number.parseInt(raw || "1", 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  }, [searchParams]);

  // 从 URL 读取 pageSize
  const pageSize = useMemo(() => {
    const raw = searchParams.get(pageSizeKey);
    const parsed = Number.parseInt(raw || String(defaultPageSize), 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : defaultPageSize;
  }, [defaultPageSize, pageSizeKey, searchParams]);

  // 本地防抖状态
  const [debouncedFilters, setDebouncedFilters] = useState<T>(filtersFromUrl);

  // 处理防抖与即时同步
  useEffect(() => {
    // 立即同步非防抖字段
    const immediateKeys = (Object.keys(filtersFromUrl) as (keyof T)[]).filter(
      (k) => !debounceKeys.includes(k),
    );

    setDebouncedFilters((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const k of immediateKeys) {
        if (next[k] !== filtersFromUrl[k]) {
          next[k] = filtersFromUrl[k];
          changed = true;
        }
      }
      return changed ? next : prev;
    });

    if (debounceKeys.length === 0) return;

    const timer = setTimeout(() => {
      setDebouncedFilters((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const k of debounceKeys) {
          if (next[k] !== filtersFromUrl[k]) {
            next[k] = filtersFromUrl[k];
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, debounceDelay);

    return () => {
      clearTimeout(timer);
    };
  }, [debounceDelay, debounceKeys, filtersFromUrl]);

  // 修改页码
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

  // 修改每页条数
  const setPageSize = useCallback(
    (nextSize: number) => {
      setSearchParams(
        (current) => {
          const nextParams = new URLSearchParams(current);
          if (nextSize === defaultPageSize) {
            nextParams.delete(pageSizeKey);
          } else {
            nextParams.set(pageSizeKey, String(nextSize));
          }
          nextParams.delete("page");
          return nextParams;
        },
        { replace: true },
      );
    },
    [defaultPageSize, pageSizeKey, setSearchParams],
  );

  // 批量更新筛选
  const setFilters = useCallback(
    (updates: Partial<T>) => {
      setSearchParams(
        (current) => {
          const nextParams = new URLSearchParams(current);
          Object.entries(updates).forEach(([key, value]) => {
            const defaultValue = defaultFilters[key];
            if (
              value === null ||
              value === undefined ||
              value === "" ||
              value === defaultValue
            ) {
              nextParams.delete(key);
            } else {
              nextParams.set(key, String(value));
            }
          });
          nextParams.delete("page");
          return nextParams;
        },
        { replace: true },
      );
    },
    [defaultFilters, setSearchParams],
  );

  // 更新单个筛选字段
  const setFilter = useCallback(
    <K extends keyof T>(key: K, value: T[K]) => {
      setFilters({ [key]: value } as unknown as Partial<T>);
    },
    [setFilters],
  );

  // 重置所有筛选
  const resetFilters = useCallback(() => {
    setSearchParams(
      (current) => {
        const nextParams = new URLSearchParams(current);
        Object.keys(defaultFilters).forEach((key) => {
          nextParams.delete(key);
        });
        nextParams.delete("page");
        return nextParams;
      },
      { replace: true },
    );
  }, [defaultFilters, setSearchParams]);

  return {
    filters: filtersFromUrl,
    debouncedFilters,
    page,
    pageSize,
    setFilter,
    setFilters,
    resetFilters,
    setPage,
    setPageSize,
  };
}
