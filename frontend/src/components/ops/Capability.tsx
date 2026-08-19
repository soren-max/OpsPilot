import { AlertTriangle, CheckCircle2, Clock3, ShieldX, X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import type { OperationCapability } from "../../services/operationCapabilities";

export function CapabilityReason({
  capability,
  compact = false,
}: {
  capability: OperationCapability;
  compact?: boolean;
}) {
  const positive = capability.outcome === "EXECUTABLE";
  const approval = capability.outcome === "APPROVAL_REQUIRED";
  const Icon = positive
    ? CheckCircle2
    : approval
      ? Clock3
      : capability.outcome === "UNAVAILABLE"
        ? AlertTriangle
        : ShieldX;
  return (
    <span
      className={`capability-reason capability-reason--${capability.outcome.toLowerCase()} ${compact ? "is-compact" : ""}`.trim()}
      data-capability-outcome={capability.outcome}
    >
      <Icon size={compact ? 13 : 15} aria-hidden="true" />
      <span>
        <strong>
          <code>{capability.action}</code> · {capability.label}
        </strong>
        {!compact && <small>{capability.reason}</small>}
      </span>
    </span>
  );
}

export function PermissionGate({
  capability,
  children,
  blockedLabel,
  className = "button button--secondary",
  showReason = true,
}: {
  capability: OperationCapability;
  children: ReactNode;
  blockedLabel: string;
  className?: string;
  showReason?: boolean;
}) {
  if (capability.canInitiate) return <>{children}</>;
  return (
    <span className="permission-gate">
      <button className={className} disabled aria-label={`${blockedLabel}：${capability.label}`}>
        {blockedLabel}
      </button>
      {showReason && <CapabilityReason capability={capability} compact />}
    </span>
  );
}

export function OperationConfirmDialog({
  open,
  action,
  environment,
  service,
  targetCount,
  capability,
  pending,
  onConfirm,
  onClose,
}: {
  open: boolean;
  action: "status" | "restart";
  environment: string;
  service: string;
  targetCount: number;
  capability: OperationCapability;
  pending: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose, open, pending]);
  if (!open) return null;
  const actionLabel = action === "status" ? "状态检查" : "重启";
  return (
    <div className="confirm-dialog-backdrop" role="presentation">
      <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <button
          className="icon-button confirm-dialog__close"
          aria-label="关闭操作确认"
          onClick={onClose}
          disabled={pending}
        >
          <X size={18} aria-hidden="true" />
        </button>
        <h2 id={titleId}>确认{actionLabel}</h2>
        <p>请核对目标和后端判定的执行语义。浏览器不会绕过审批或执行门禁。</p>
        <dl>
          <div>
            <dt>环境</dt>
            <dd>{environment}</dd>
          </div>
          <div>
            <dt>服务</dt>
            <dd>{service}</dd>
          </div>
          <div>
            <dt>目标主机</dt>
            <dd>{targetCount} 台</dd>
          </div>
          <div>
            <dt>操作语义</dt>
            <dd>
              <CapabilityReason capability={capability} />
            </dd>
          </div>
        </dl>
        <div className="confirm-dialog__actions">
          <button
            ref={cancelRef}
            className="button button--secondary"
            onClick={onClose}
            disabled={pending}
          >
            取消
          </button>
          <button
            className="button button--primary"
            onClick={onConfirm}
            disabled={pending || !capability.canInitiate}
          >
            {pending
              ? "正在提交…"
              : capability.requiresApproval
                ? "提交审批"
                : `确认${actionLabel}`}
          </button>
        </div>
      </section>
    </div>
  );
}
