import { useEffect, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./auth/authContext";
import { LoadingState } from "./components/PageState";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      try {
        sessionStorage.setItem("opspilot_redirect", location.pathname + location.search);
      } catch {
        /* ignore */
      }
    }
  }, [isLoading, isAuthenticated, location.pathname, location.search]);

  if (isLoading) {
    return <LoadingState label="正在验证登录状态" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export function GuestRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingState label="正在验证登录状态" />;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
