import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { authApi, TOKEN_KEY } from "./api";
import { AuthContext } from "./auth/authContext";
import { queryKeys } from "./query/queryKeys";

function getStoredToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const {
    data: user,
    isLoading,
    isError,
  } = useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: async () => {
      if (!getStoredToken()) return null;
      try {
        return await authApi.me();
      } catch {
        try {
          localStorage.removeItem(TOKEN_KEY);
          sessionStorage.removeItem(TOKEN_KEY);
        } catch {
          /* ignore */
        }
        return null;
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const isAuthenticated = !!user && !isError;

  const login = useCallback(
    async (username: string, password: string) => {
      const result = await authApi.login(username, password);
      try {
        localStorage.setItem(TOKEN_KEY, result.access_token);
      } catch {
        /* ignore */
      }
      const currentUser = await authApi.me();
      queryClient.setQueryData(queryKeys.auth.me, currentUser);
      const redirect = sessionStorage.getItem("opspilot_redirect") ?? "/";
      sessionStorage.removeItem("opspilot_redirect");
      navigate(redirect, { replace: true });
    },
    [queryClient, navigate],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    }
    try {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem("opspilot_redirect");
    } catch {
      /* ignore */
    }
    queryClient.setQueryData(queryKeys.auth.me, null);
    queryClient.clear();
    navigate("/login", { replace: true });
  }, [queryClient, navigate]);

  return (
    <AuthContext.Provider value={{ user: user ?? null, isLoading, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
