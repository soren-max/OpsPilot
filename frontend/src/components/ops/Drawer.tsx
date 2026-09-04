/* eslint-disable react-refresh/only-export-components -- sanitization is part of the drawer contract */
import { Check, Copy, ShieldCheck, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

export function DetailDrawer({
  open,
  title,
  subtitle,
  className = "",
  children,
  onClose,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  className?: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const titleId = useId();
  const drawerRef = useRef<HTMLElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    const drawer = drawerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawer?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
      if (event.key !== "Tab" || !drawer) return;
      const focusable = Array.from(
        drawer.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [contenteditable="true"], [tabindex="0"]',
        ),
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus.current?.focus();
    };
  }, [open]);
  if (!open) return null;
  return (
    <div className="drawer-layer" role="presentation">
      <div className="drawer-layer__backdrop" aria-hidden="true" onClick={onClose} />
      <aside
        ref={drawerRef}
        className={`detail-drawer ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="detail-drawer__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" aria-label="关闭详情" onClick={onClose}>
            <X size={19} aria-hidden="true" />
          </button>
        </header>
        <div className="detail-drawer__body">{children}</div>
      </aside>
    </div>
  );
}

const sensitiveKey = /token|secret|password|credential|private[_-]?key|authorization|cookie/i;

export function sanitizeTechnicalData(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeTechnicalData);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        sensitiveKey.test(key) ? "[REDACTED]" : sanitizeTechnicalData(item),
      ]),
    );
  }
  return value;
}

export function CopyableId({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard?.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1_500);
  };
  return (
    <span className="copyable-id">
      {label && <span>{label}</span>}
      <code title={value}>{value}</code>
      <button type="button" onClick={() => void copy()} aria-label={`复制${label ?? "标识符"}`}>
        {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
        <span>{copied ? "已复制" : "复制"}</span>
      </button>
    </span>
  );
}

export function TechnicalDetailDrawer({
  open,
  title,
  subtitle,
  identifiers = [],
  detail,
  children,
  onClose,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  identifiers?: Array<{ label: string; value: string | null | undefined }>;
  detail?: unknown;
  children?: ReactNode;
  onClose: () => void;
}) {
  const safeDetail = sanitizeTechnicalData(detail);
  return (
    <DetailDrawer
      open={open}
      title={title}
      subtitle={subtitle}
      className="technical-detail-drawer"
      onClose={onClose}
    >
      <div className="technical-detail-drawer__trust">
        <ShieldCheck size={16} aria-hidden="true" />
        <span>Technical detail is read-only. Known secret fields are redacted.</span>
      </div>
      {identifiers.length ? (
        <div className="technical-detail-drawer__ids">
          {identifiers.map(({ label, value }) =>
            value ? <CopyableId key={label} label={label} value={value} /> : null,
          )}
        </div>
      ) : null}
      {children}
      {detail !== undefined ? (
        <pre className="technical-detail-drawer__payload">
          {JSON.stringify(safeDetail, null, 2)}
        </pre>
      ) : null}
    </DetailDrawer>
  );
}
