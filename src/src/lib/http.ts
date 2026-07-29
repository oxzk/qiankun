import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from "axios";
import { storage } from "@/lib/storage";
import type { ApiResponse } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
export const API_PREFIX = import.meta.env.VITE_API_PREFIX || "/api";

/**
 * 创建 HTTP 客户端。
 */
function createHttpClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 60000,
  });

  instance.interceptors.request.use((config) => {
    const token = storage.getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  instance.interceptors.response.use(
    (response) => response,
    (error: AxiosError<ApiResponse<unknown>>) => {
      if (error.response?.status === 401) {
        storage.clearSession();
        window.dispatchEvent(new CustomEvent("qiankun:unauthorized"));
      }
      return Promise.reject(error);
    },
  );

  return instance;
}

export const http = createHttpClient();

/**
 * 清理空查询参数。
 */
export function compactParams(params: object): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params as Record<string, unknown>).filter(
      ([, value]) => value !== undefined && value !== null && value !== "",
    ),
  );
}

/**
 * 提取统一响应数据。
 */
export async function unwrap<T>(request: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  const response = await request;
  if (!response.data.success) throw new Error(response.data.message || "请求失败");
  return response.data.data as T;
}

/**
 * 附带 AbortSignal 的请求配置。
 */
export function withSignal(signal?: AbortSignal): AxiosRequestConfig | undefined {
  return signal ? { signal } : undefined;
}

/**
 * 提取错误消息。
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiResponse<unknown>>(error)) {
    if (error.code === "ERR_CANCELED" || error.name === "CanceledError") return "请求已取消";
    return error.response?.data?.message || error.message || "请求失败";
  }
  if (error instanceof Error) return error.message;
  return "请求失败";
}
