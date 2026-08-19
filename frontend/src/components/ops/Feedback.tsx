import { AlertTriangle, CheckCircle2, Info, Search, X, XCircle } from "lucide-react";
import type { ReactNode } from "react";

export function FilterBar({
  children,
  ariaLabel = "筛选和搜索",
}: {
  children: ReactNode;
  ariaLabel?: string;
}) {
  return (
    <div className="filter-bar" role="search" aria-label={ariaLabel}>
      {children}
    </div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = "搜索",
  ariaLabel = "搜索",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
}) {
  return (
    <label className="search-input">
      <Search size={16} aria-hidden="true" />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
      />
    </label>
  );
}

export function ToolbarActions({ children }: { children: ReactNode }) {
  return <div className="toolbar-actions">{children}</div>;
}

export function ConfirmationBanner({ children }: { children: ReactNode }) {
  return (
    <div className="confirmation-banner">
      <Info size={17} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export function InlineNotice({
  title,
  children,
  tone = "info",
}: {
  title: string;
  children: ReactNode;
  tone?: "info" | "success" | "warning" | "danger";
}) {
  const Icon =
    tone === "danger"
      ? XCircle
      : tone === "warning"
        ? AlertTriangle
        : tone === "success"
          ? CheckCircle2
          : Info;
  return (
    <div
      className={`inline-notice inline-notice--${tone}`}
      role={tone === "danger" ? "alert" : "note"}
    >
      <Icon size={17} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <span>{children}</span>
      </div>
    </div>
  );
}

export function Toast({
  title,
  message,
  onClose,
  tone = "success",
}: {
  title: string;
  message: string;
  onClose: () => void;
  tone?: "success" | "danger" | "warning" | "info";
}) {
  const Icon =
    tone === "danger"
      ? XCircle
      : tone === "warning"
        ? AlertTriangle
        : tone === "info"
          ? Info
          : CheckCircle2;
  return (
    <div
      className={`toast toast--${tone}`}
      role={tone === "danger" ? "alert" : "status"}
      aria-live={tone === "danger" ? "assertive" : "polite"}
    >
      <Icon size={18} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <span>{message}</span>
      </div>
      <button className="icon-button" aria-label="关闭通知" onClick={onClose}>
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
