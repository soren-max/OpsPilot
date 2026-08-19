import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { authApi, catalogApi, systemApi } from "./api";
import { AuthProvider } from "./AuthContext";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ErrorState, LoadingState } from "./components/PageState";
import { ProtectedRoute, GuestRoute } from "./ProtectedRoute";
import { ThemeProvider } from "./theme/ThemeProvider";
import { queryKeys } from "./query/queryKeys";
import {
  readEnvironmentPreference,
  writeEnvironmentPreference,
} from "./services/environmentPreference";
import { resolveOperationCapabilities } from "./services/operationCapabilities";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const AuditsPage = lazy(() =>
  import("./pages/AuditsPage").then((module) => ({ default: module.AuditsPage })),
);
const AccessControlPage = lazy(() =>
  import("./pages/AccessControlPage").then((module) => ({ default: module.AccessControlPage })),
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const HostsPage = lazy(() =>
  import("./pages/HostsPage").then((module) => ({ default: module.HostsPage })),
);
const ServicesPage = lazy(() =>
  import("./pages/ServicesPage").then((module) => ({ default: module.ServicesPage })),
);
const TasksPage = lazy(() =>
  import("./pages/TasksPage").then((module) => ({ default: module.TasksPage })),
);
const IncidentsPage = lazy(() =>
  import("./pages/IncidentsPage").then((module) => ({ default: module.IncidentsPage })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })),
);

function ProtectedApp() {
  const environments = useQuery({
    queryKey: queryKeys.environments,
    queryFn: catalogApi.environments,
  });
  const security = useQuery({
    queryKey: queryKeys.auth.status,
    queryFn: authApi.status,
  });
  const readiness = useQuery({
    queryKey: queryKeys.system.ready,
    queryFn: systemApi.ready,
    refetchInterval: 15_000,
  });
  const [environmentId, setEnvironmentId] = useState(readEnvironmentPreference);

  useEffect(() => {
    if (!environments.data) return;
    const selectedIsAvailable = environments.data.some(
      (item) => item.id === environmentId && item.enabled,
    );
    if (selectedIsAvailable) return;
    const fallback = environments.data.find((item) => item.enabled)?.id ?? "";
    setEnvironmentId(fallback);
    if (fallback) writeEnvironmentPreference(fallback);
  }, [environmentId, environments.data]);

  const selectEnvironment = (id: string) => {
    setEnvironmentId(id);
    writeEnvironmentPreference(id);
  };

  if (environments.isLoading || security.isLoading)
    return <LoadingState label="正在连接 OpsPilot" />;
  if (environments.error || security.error) {
    return (
      <ErrorState
        error={(environments.error ?? security.error)!}
        onRetry={() => {
          void environments.refetch();
          void security.refetch();
        }}
      />
    );
  }
  const currentEnvironment = environments.data?.find((item) => item.id === environmentId);
  const environmentName = currentEnvironment?.name ?? "当前环境";
  const environmentLevel = currentEnvironment?.environment_level ?? "DEVELOPMENT";
  const operationCapabilities = resolveOperationCapabilities({
    security: security.data!,
    readiness: readiness.data,
    readinessUnavailable: !readiness.data || Boolean(readiness.error),
    environment: currentEnvironment,
  });

  if (!environmentId) {
    return <ErrorState error={new Error("没有可用环境。请先配置逻辑执行目标目录。")} />;
  }

  return (
    <AppShell
      environments={environments.data ?? []}
      environmentId={environmentId}
      onEnvironmentChange={selectEnvironment}
      security={security.data!}
      capabilities={operationCapabilities}
    >
      <Routes>
        <Route
          path="/"
          element={
            <DashboardPage
              environmentId={environmentId}
              environmentName={environmentName}
              environmentLevel={environmentLevel}
              security={security.data!}
              readiness={readiness.data}
              readinessError={readiness.error}
              capabilities={operationCapabilities}
            />
          }
        />
        <Route
          path="/services"
          element={
            <ServicesPage
              environmentId={environmentId}
              environmentName={environmentName}
              environmentLevel={environmentLevel}
              capabilities={operationCapabilities}
            />
          }
        />
        <Route
          path="/hosts"
          element={
            <HostsPage
              environmentId={environmentId}
              environmentName={environmentName}
              environments={environments.data ?? []}
              onEnvironmentChange={selectEnvironment}
            />
          }
        />
        <Route
          path="/incidents/:incidentId?"
          element={<IncidentsPage environment={currentEnvironment?.code ?? environmentName} />}
        />
        <Route
          path="/tasks"
          element={<TasksPage environmentId={environmentId} security={security.data!} />}
        />
        <Route path="/audits" element={<AuditsPage environmentId={environmentId} />} />
        <Route
          path="/access"
          element={<AccessControlPage capabilities={operationCapabilities} />}
        />
        <Route
          path="/settings"
          element={
            <SettingsPage
              security={security.data!}
              readiness={readiness.data}
              readinessError={readiness.error}
              onRetryReadiness={() => void readiness.refetch()}
              capabilities={operationCapabilities}
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <Suspense fallback={<LoadingState label="正在加载页面模块" />}>
            <Routes>
              <Route
                path="/login"
                element={
                  <GuestRoute>
                    <LoginPage />
                  </GuestRoute>
                }
              />
              <Route
                path="/*"
                element={
                  <ProtectedRoute>
                    <ProtectedApp />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </Suspense>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
