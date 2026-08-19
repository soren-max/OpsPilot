import {
  Activity,
  Boxes,
  ClipboardList,
  Siren,
  FileClock,
  LayoutDashboard,
  LogOut,
  Network,
  Server,
  Settings,
  ShieldCheck,
  UserRound,
  Wrench,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/authContext";
import { Breadcrumbs } from "./Breadcrumbs";
import { NetworkStatusBanner } from "./PageState";
import { ThemeSwitcher } from "./ThemeSwitcher";
import type { Environment } from "../types";
import type { SecurityContext } from "../types";
import type { OperationCapabilities } from "../services/operationCapabilities";

const primaryNav = [
  ["/", "运维总览", LayoutDashboard],
  ["/services", "服务管理", Wrench],
  ["/hosts", "主机管理", Server],
  ["/incidents", "事件中心", Siren],
  ["/tasks", "任务中心", ClipboardList],
  ["/audits", "操作审计", FileClock],
  ["/access", "权限管理", ShieldCheck],
  ["/settings", "系统配置", Settings],
] as const;

const futureNav = [
  ["服务拓扑", Network],
  ["巡检中心", Boxes],
] as const;

export function AppShell({
  children,
  environments,
  environmentId,
  onEnvironmentChange,
  security,
  capabilities,
}: {
  children: ReactNode;
  environments: Environment[];
  environmentId: string;
  onEnvironmentChange: (id: string) => void;
  security: SecurityContext;
  capabilities: OperationCapabilities;
}) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const currentEnvironment = environments.find((item) => item.id === environmentId);
  const isProduction = currentEnvironment?.environment_level === "PRODUCTION";
  const isAnsible = security.executor === "ansible";
  const writeSummary = `restart：${capabilities.restart.label}`;
  useEffect(() => {
    if (location.hash) {
      window.requestAnimationFrame(() =>
        document.querySelector<HTMLElement>(location.hash)?.scrollIntoView({ block: "start" }),
      );
      return;
    }
    document.querySelector<HTMLElement>("#main-content")?.focus();
  }, [location.pathname, location.hash]);
  return (
    <div className="ops-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <NetworkStatusBanner />
      <aside className="ops-sidebar">
        <div className="ops-brand">
          <span>
            <Activity size={21} aria-hidden="true" />
          </span>
          <div>
            <strong>OPSPILOT</strong>
            <small>云原生运维控制台</small>
          </div>
        </div>
        <p className="nav-label">运行管理</p>
        <nav aria-label="运行管理">
          {primaryNav.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              <Icon size={17} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <p className="nav-label nav-label--future">规划能力</p>
        <div className="future-nav">
          {futureNav.map(([label, Icon]) => (
            <span key={label}>
              <Icon size={17} aria-hidden="true" />
              <span>{label}</span>
              <small>规划中</small>
            </span>
          ))}
        </div>
        <div className={`executor-notice ${isAnsible ? "is-integration" : ""}`}>
          <ShieldCheck size={17} aria-hidden="true" />
          <div>
            <strong>
              {isAnsible ? "受控 Ansible 执行" : "安全模拟模式"}
            </strong>
            <small>
              {security.executor} · {writeSummary}
            </small>
          </div>
        </div>
      </aside>
      <div className="ops-main">
        <header className="global-bar">
          <div
            className={`global-bar__execution ${isAnsible ? "is-integration" : ""}`}
            role="status"
          >
            <span className="global-bar__shield">
              <ShieldCheck size={17} aria-hidden="true" />
            </span>
            <strong>
              {isAnsible ? "受控 Ansible 执行" : "模拟执行环境"}
            </strong>
            <b>{security.executor}</b>
            <span>
              {isAnsible ? "Structured Action → Policy → Ansible → Verify" : writeSummary}
            </span>
          </div>
          <div className="global-bar__tools">
            <label className="environment-control">
              <span className="environment-control__meta">环境</span>
              <select
                value={environmentId}
                onChange={(event) => onEnvironmentChange(event.target.value)}
              >
                {environments.map((item) => (
                  <option value={item.id} disabled={!item.enabled} key={item.id}>
                    {item.name}
                    {item.enabled ? "" : "（停用）"}
                  </option>
                ))}
              </select>
            </label>
            <span className={`top-status-chip ${isProduction ? "is-production" : ""}`}>
              <span aria-hidden="true" />
              {isProduction ? "生产" : "非生产"}
            </span>
            <span className="top-status-chip">
              <span aria-hidden="true" />
              {security.executor}
            </span>
            <span
              className="top-status-chip is-safe"
              title={capabilities.restart.reason}
            >
              <ShieldCheck size={14} aria-hidden="true" />
              {capabilities.restart.label}
            </span>
            <ThemeSwitcher />
            <span
              className="user-chip"
              aria-label={`当前用户：${user?.display_name ?? ""} ${user?.username ?? ""}`}
            >
              <span className="user-chip__avatar">
                <UserRound size={17} aria-hidden="true" />
              </span>
              <span className="user-chip__copy">
                <strong>{user?.display_name ?? "未记录"}</strong>
                <small>{user?.username ?? "未记录"}</small>
              </span>
            </span>
            <button
              className="top-action-btn"
              onClick={logout}
              aria-label="退出登录"
              title="退出登录"
            >
              <LogOut size={16} aria-hidden="true" />
            </button>
          </div>
        </header>
        <main id="main-content" className="ops-content" tabIndex={0}>
          <Breadcrumbs />
          {children}
        </main>
      </div>
    </div>
  );
}
