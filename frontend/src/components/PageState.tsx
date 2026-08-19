import { AlertCircle, Inbox, LoaderCircle, RotateCcw, ShieldX, WifiOff } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "../api";

export function LoadingState({
  label = "正在加载数据",
  variant = "compact",
}: {
  label?: string;
  variant?: "compact" | "table" | "cards";
}) {
  if (variant !== "compact") {
    const count = variant === "table" ? 5 : 4;
    return (
      <div className={`skeleton-state skeleton-state--${variant}`} role="status" aria-label={label}>
        {Array.from({ length: count }, (_, index) => (
          <span key={index} />
        ))}
      </div>
    );
  }
  return (
    <div className="page-state" role="status">
      <LoaderCircle className="spin" size={20} aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const requestId = error instanceof ApiError ? error.requestId : undefined;
  const forbidden = error instanceof ApiError && error.status === 403;
  const network =
    error instanceof ApiError && (error.code === "NETWORK_ERROR" || error.serviceUnavailable);
  const Icon = forbidden ? ShieldX : network ? WifiOff : AlertCircle;
  const title = forbidden ? "权限不足" : network ? "网络或服务连接异常" : "数据加载失败";
  return (
    <div className="page-state page-state--error" role="alert">
      <Icon size={20} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <span>{error.message}</span>
        {requestId && <small>Request ID：{requestId}</small>}
      </div>
      {onRetry && (
        <button className="button button--secondary" onClick={onRetry}>
          <RotateCcw size={15} aria-hidden="true" /> 重试
        </button>
      )}
    </div>
  );
}

export function NetworkStatusBanner() {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);
  if (online) return null;
  return (
    <div className="network-status-banner" role="alert">
      <WifiOff size={16} aria-hidden="true" />
      <strong>网络已断开</strong>
      <span>当前数据可能已过期；连接恢复后可重试加载。</span>
    </div>
  );
}

export function EmptyState({
  message,
  title = "暂无数据",
  action,
}: {
  message: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <Inbox size={22} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <span>{message}</span>
      </div>
      {action}
    </div>
  );
}
