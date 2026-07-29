import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { authApi } from "@/lib/api";
import { TOKEN_EXPIRY_WARN_MS } from "@/lib/query-options";
import { getTokenRemainingMs, persistLoginSession, readValidLocalSession } from "@/lib/session";
import { storage } from "@/lib/storage";
import { LOGIN_PATH, buildLoginPath, isLoginPath, readProtectedPath } from "@/routes";
import type { TokenResponse, User } from "@/types";

export interface SessionContextValue {
  /**
   * 会话是否已完成初始化校验。
   */
  ready: boolean;
  /**
   * 当前是否已登录。
   */
  loggedIn: boolean;
  /**
   * 当前登录用户。
   */
  user: User | null;
  /**
   * 完成登录状态同步。
   */
  completeLogin: (token: TokenResponse) => void;
  /**
   * 退出登录并清理本地会话。
   */
  logout: () => void;
}

export interface SessionProviderProps {
  /**
   * 需要访问会话状态的子节点。
   */
  children: ReactNode;
}

const SessionContext = createContext<SessionContextValue | null>(null);

/**
 * 登录会话状态提供器。
 */
export function SessionProvider({ children }: SessionProviderProps): JSX.Element {
  const localSession = readValidLocalSession();
  const [ready, setReady] = useState(() => !localSession);
  const [loggedIn, setLoggedIn] = useState(() => Boolean(localSession));
  const [user, setUser] = useState<User | null>(() => localSession?.user ?? null);
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const unauthorizedHandledRef = useRef(false);
  const expiryTimerRef = useRef<number | null>(null);
  const warnTimerRef = useRef<number | null>(null);
  const locationRef = useRef(location);
  const bootstrappedRef = useRef(false);

  locationRef.current = location;

  /**
   * 清理本地会话与查询缓存。
   */
  const clearSession = useCallback((): void => {
    storage.clearSession();
    setLoggedIn(false);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  /**
   * 清理令牌到期计时器。
   */
  const clearExpiryTimers = useCallback((): void => {
    if (expiryTimerRef.current !== null) {
      window.clearTimeout(expiryTimerRef.current);
      expiryTimerRef.current = null;
    }
    if (warnTimerRef.current !== null) {
      window.clearTimeout(warnTimerRef.current);
      warnTimerRef.current = null;
    }
  }, []);

  /**
   * 因过期或失效跳转登录页。
   */
  const redirectToLogin = useCallback(
    (title: string): void => {
      const current = locationRef.current;
      if (!isLoginPath(current.pathname)) {
        navigate(buildLoginPath(readProtectedPath(current)), { replace: true });
        toast({ title, description: "请重新登录", variant: "destructive" });
      }
    },
    [navigate, toast],
  );

  /**
   * 安排令牌到期提醒与自动登出。
   */
  const scheduleExpiryTimers = useCallback((): void => {
    clearExpiryTimers();
    const remainingMs = getTokenRemainingMs();
    if (remainingMs === null) return;

    if (remainingMs <= 0) {
      unauthorizedHandledRef.current = true;
      clearSession();
      redirectToLogin("登录已过期");
      return;
    }

    if (remainingMs > TOKEN_EXPIRY_WARN_MS) {
      warnTimerRef.current = window.setTimeout(() => {
        toast({
          title: "登录即将过期",
          description: "请尽快保存工作并重新登录",
        });
      }, remainingMs - TOKEN_EXPIRY_WARN_MS);
    }

    expiryTimerRef.current = window.setTimeout(() => {
      unauthorizedHandledRef.current = true;
      clearSession();
      redirectToLogin("登录已过期");
    }, remainingMs);
  }, [clearExpiryTimers, clearSession, redirectToLogin, toast]);

  useEffect(() => {
    if (bootstrappedRef.current) return;
    bootstrappedRef.current = true;
    let cancelled = false;

    async function bootstrap(): Promise<void> {
      const session = readValidLocalSession();
      if (!session) {
        if (!cancelled) {
          setLoggedIn(false);
          setUser(null);
          setReady(true);
        }
        return;
      }

      try {
        const me = await authApi.me();
        if (cancelled) return;
        storage.setUser(me);
        setUser(me);
        setLoggedIn(true);
        unauthorizedHandledRef.current = false;
        scheduleExpiryTimers();
      } catch {
        if (cancelled) return;
        clearSession();
      } finally {
        if (!cancelled) setReady(true);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
    // 仅启动时校验一次会话
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      if (unauthorizedHandledRef.current) return;
      unauthorizedHandledRef.current = true;
      clearExpiryTimers();
      clearSession();
      redirectToLogin("登录已失效");
    };
    window.addEventListener("qiankun:unauthorized", onUnauthorized);
    return () => window.removeEventListener("qiankun:unauthorized", onUnauthorized);
  }, [clearExpiryTimers, clearSession, redirectToLogin]);

  useEffect(() => () => clearExpiryTimers(), [clearExpiryTimers]);

  const completeLogin = useCallback(
    (token: TokenResponse): void => {
      unauthorizedHandledRef.current = false;
      const snapshot = persistLoginSession(token);
      setUser(snapshot.user);
      setLoggedIn(true);
      setReady(true);
      scheduleExpiryTimers();
    },
    [scheduleExpiryTimers],
  );

  const logout = useCallback((): void => {
    unauthorizedHandledRef.current = false;
    clearExpiryTimers();
    clearSession();
    navigate(LOGIN_PATH, { replace: true });
    toast({ title: "已退出登录" });
  }, [clearExpiryTimers, clearSession, navigate, toast]);

  const value = useMemo<SessionContextValue>(
    () => ({ ready, loggedIn, user, completeLogin, logout }),
    [completeLogin, loggedIn, logout, ready, user],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/**
 * 读取当前登录会话状态。
 */
export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used within SessionProvider");
  return value;
}
