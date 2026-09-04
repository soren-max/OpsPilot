import {
  Activity,
  ClipboardList,
  Siren,
  FileClock,
  LayoutDashboard,
  LogOut,
  Menu,
  Server,
  Settings,
  ShieldCheck,
  UserRound,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/authContext";
import { Breadcrumbs } from "./Breadcrumbs";
import { NetworkStatusBanner } from "./PageState";
import { ThemeSwitcher } from "./ThemeSwitcher";
import type { Environment } from "../types";
import type { SecurityContext } from "../types";
import type { OperationCapabilities } from "../services/operationCapabilities";

const navGroups = [
  {
    label: "Operations",
    items: [
      ["/", "Overview", LayoutDashboard],
      ["/incidents", "Incidents", Siren],
      ["/tasks", "Executions", ClipboardList],
      ["/audits", "Audit", FileClock],
    ],
  },
  {
    label: "Inventory",
    items: [
      ["/services", "Services", Wrench],
      ["/hosts", "Hosts", Server],
    ],
  },
  {
    label: "Platform",
    items: [
      ["/access", "Capabilities", ShieldCheck],
      ["/settings", "Settings", Settings],
    ],
  },
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
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLButtonElement>(null);
  const mobileCloseRef = useRef<HTMLButtonElement>(null);
  const currentEnvironment = environments.find((item) => item.id === environmentId);
  const isProduction = currentEnvironment?.environment_level === "PRODUCTION";
  const isAnsible = security.executor === "ansible";
  const writeSummary = `restart：${capabilities.restart.label}`;
  useEffect(() => {
    setMobileNavigationOpen(false);
    if (location.hash) {
      window.requestAnimationFrame(() =>
        document.querySelector<HTMLElement>(location.hash)?.scrollIntoView({ block: "start" }),
      );
      return;
    }
    document.querySelector<HTMLElement>("#main-content")?.focus();
  }, [location.pathname, location.hash]);
  useEffect(() => {
    if (!mobileNavigationOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    mobileCloseRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileNavigationOpen(false);
        mobileMenuRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileNavigationOpen]);
  return (
    <div className={`ops-shell ${mobileNavigationOpen ? "has-mobile-navigation" : ""}`}>
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <NetworkStatusBanner />
      <button
        className="mobile-nav-backdrop"
        aria-label="Close navigation"
        tabIndex={mobileNavigationOpen ? 0 : -1}
        onClick={() => setMobileNavigationOpen(false)}
      />
      <aside
        id="primary-navigation"
        className={`ops-sidebar ${mobileNavigationOpen ? "is-open" : ""}`}
        aria-label="Primary navigation"
      >
        <div className="ops-brand">
          <span>
            <Activity size={21} aria-hidden="true" />
          </span>
          <div>
            <strong>OPSPILOT</strong>
            <small>AI / SRE Operations</small>
          </div>
          <button
            ref={mobileCloseRef}
            className="mobile-nav-close icon-button"
            type="button"
            aria-label="Close navigation"
            onClick={() => {
              setMobileNavigationOpen(false);
              mobileMenuRef.current?.focus();
            }}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        {navGroups.map((group) => (
          <div className="nav-group" key={group.label}>
            <p className="nav-label">{group.label}</p>
            <nav aria-label={group.label}>
              {group.items.map(([to, label, Icon]) => (
                <NavLink key={to} to={to} end={to === "/"}>
                  <Icon size={17} aria-hidden="true" />
                  <span>{label}</span>
                </NavLink>
              ))}
            </nav>
          </div>
        ))}
        <div className={`executor-notice ${isAnsible ? "is-integration" : ""}`}>
          <ShieldCheck size={17} aria-hidden="true" />
          <div>
            <strong>{isAnsible ? "受控 Ansible 执行" : "安全模拟模式"}</strong>
            <small>
              {security.executor} · {writeSummary}
            </small>
          </div>
        </div>
      </aside>
      <div className="ops-main">
        <header className="global-bar">
          <button
            ref={mobileMenuRef}
            className="mobile-nav-toggle icon-button"
            type="button"
            aria-label="Open navigation"
            aria-controls="primary-navigation"
            aria-expanded={mobileNavigationOpen}
            onClick={() => setMobileNavigationOpen(true)}
          >
            <Menu size={19} aria-hidden="true" />
          </button>
          <div
            className={`global-bar__execution ${isAnsible ? "is-integration" : ""}`}
            role="status"
          >
            <span className="global-bar__shield">
              <ShieldCheck size={17} aria-hidden="true" />
            </span>
            <strong>{isAnsible ? "受控 Ansible 执行" : "模拟执行环境"}</strong>
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
            <span className="top-status-chip is-safe" title={capabilities.restart.reason}>
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
