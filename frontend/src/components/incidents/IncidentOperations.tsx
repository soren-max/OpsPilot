/* eslint-disable react-refresh/only-export-components -- incident formatting is shared with its page */
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  FileClock,
  FileText,
  HeartPulse,
  ListChecks,
  ScrollText,
  ServerCog,
  ShieldCheck,
  ShieldQuestion,
  TerminalSquare,
  X,
  XCircle,
} from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type {
  ApprovalRequest,
  ExecutionRecord,
  Incident,
  IncidentEvidence,
  TimelineItem,
  WorkflowRun,
} from "../../types";
import { CopyableId } from "../ops/Drawer";
import { StatusBadge } from "../ops/Status";

export function formatIncidentDate(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

type LifecycleState = "COMPLETE" | "ACTIVE" | "WAITING" | "FAILED" | "SKIPPED";

const lifecycleIcon: Record<LifecycleState, typeof Check> = {
  COMPLETE: Check,
  ACTIVE: Activity,
  WAITING: Clock3,
  FAILED: XCircle,
  SKIPPED: CircleDashed,
};

export function LifecycleRail({
  incident,
  workflows,
  approvals,
  executions,
}: {
  incident: Incident;
  workflows: WorkflowRun[];
  approvals: ApprovalRequest[];
  executions: ExecutionRecord[];
}) {
  const latestWorkflow = workflows[0];
  const latestApproval = approvals[0];
  const latestExecution = executions[0];
  const executionUnknown = ["UNKNOWN", "RECONCILIATION_REQUIRED"].includes(
    latestExecution?.status ?? "",
  );
  const executionFailed = latestExecution?.status === "FAILED";
  const verificationFailed = latestExecution?.verification_status === "FAILED";
  const terminalIncident = ["RESOLVED", "CLOSED"].includes(incident.status);

  const steps: Array<{
    label: string;
    detail: string;
    href: string;
    state: LifecycleState;
  }> = [
    {
      label: "Observe",
      detail: `${incident.evidence.length} evidence`,
      href: "#evidence",
      state: incident.evidence.length ? "COMPLETE" : "ACTIVE",
    },
    {
      label: "Investigate",
      detail: latestWorkflow?.current_node ?? "Awaiting workflow",
      href: "#investigation",
      state:
        incident.hypotheses.length || incident.diagnoses.length
          ? "COMPLETE"
          : latestWorkflow?.status === "FAILED"
            ? "FAILED"
            : latestWorkflow
              ? "ACTIVE"
              : "WAITING",
    },
    {
      label: "Diagnose",
      detail: incident.diagnoses.length ? "Grounded diagnosis" : "No diagnosis yet",
      href: "#diagnosis",
      state: incident.diagnoses.length
        ? "COMPLETE"
        : latestWorkflow?.status === "FAILED"
          ? "FAILED"
          : "WAITING",
    },
    {
      label: "Policy",
      detail: latestWorkflow?.state_references.risk_level ?? "Awaiting proposal",
      href: "#action-proposal",
      state: latestWorkflow?.state_references.risk_level
        ? "COMPLETE"
        : incident.diagnoses.length
          ? "ACTIVE"
          : "WAITING",
    },
    {
      label: "Approval",
      detail: latestApproval?.status ?? "Not requested",
      href: "#approval",
      state:
        latestApproval?.status === "APPROVED"
          ? "COMPLETE"
          : latestApproval?.status === "REJECTED"
            ? "FAILED"
            : latestApproval?.status === "PENDING"
              ? "WAITING"
              : latestExecution || terminalIncident
                ? "SKIPPED"
                : "WAITING",
    },
    {
      label: "Execute",
      detail: latestExecution?.status ?? "Not submitted",
      href: "#execution",
      state: executionFailed
        ? "FAILED"
        : executionUnknown
          ? "WAITING"
          : latestExecution?.status === "SUCCEEDED"
            ? "COMPLETE"
            : latestExecution?.status === "RUNNING"
              ? "ACTIVE"
              : terminalIncident && !latestExecution
                ? "SKIPPED"
                : "WAITING",
    },
    {
      label: "Verify",
      detail: latestExecution?.verification_status ?? "Not started",
      href: "#verification",
      state: verificationFailed
        ? "FAILED"
        : ["SUCCEEDED", "SUCCESS", "VERIFIED"].includes(latestExecution?.verification_status ?? "")
          ? "COMPLETE"
          : latestExecution?.status === "SUCCEEDED"
            ? "ACTIVE"
            : terminalIncident && !latestExecution
              ? "SKIPPED"
              : "WAITING",
    },
  ];

  return (
    <nav className="lifecycle-rail" aria-label="Incident lifecycle">
      <div className="lifecycle-rail__heading">
        <span>Incident lifecycle</span>
        <small>Navigate governed response stages</small>
      </div>
      <ol>
        {steps.map((step, index) => {
          const Icon = lifecycleIcon[step.state];
          return (
            <li key={step.label} className={`is-${step.state.toLowerCase()}`}>
              <a href={step.href} aria-label={`${step.label}: ${step.state}`}>
                <span className="lifecycle-rail__marker">
                  <Icon size={14} aria-hidden="true" />
                </span>
                <span className="lifecycle-rail__copy">
                  <strong>
                    <b>{index + 1}</b> {step.label}
                  </strong>
                  <small>{step.detail}</small>
                </span>
                <span className="lifecycle-rail__state">{step.state}</span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

const evidencePresentation: Record<
  string,
  { label: string; icon: typeof BarChart3; trust: string }
> = {
  METRIC: { label: "Metric", icon: BarChart3, trust: "Observed metric" },
  LOG: { label: "Log", icon: TerminalSquare, trust: "Untrusted external log content" },
  TICKET: { label: "Ticket", icon: FileText, trust: "External ticket context" },
  SERVICE_STATUS: { label: "Service status", icon: HeartPulse, trust: "Observed health state" },
};

export function EvidenceCard({
  evidence,
  onInspect,
}: {
  evidence: IncidentEvidence;
  onInspect: (evidence: IncidentEvidence) => void;
}) {
  const presentation = evidencePresentation[evidence.evidence_type] ?? {
    label: evidence.evidence_type,
    icon: FileText,
    trust: "External observation",
  };
  const Icon = presentation.icon;
  return (
    <article id={`evidence-${evidence.id}`} className="evidence-card">
      <header>
        <span className="evidence-card__type">
          <Icon size={15} aria-hidden="true" /> {presentation.label}
        </span>
        <time dateTime={evidence.observed_at}>{formatIncidentDate(evidence.observed_at)}</time>
      </header>
      <strong>{evidence.summary}</strong>
      <dl>
        <div>
          <dt>Source</dt>
          <dd>{evidence.source}</dd>
        </div>
        <div>
          <dt>Provenance</dt>
          <dd>{evidence.collector}</dd>
        </div>
      </dl>
      <div className="evidence-card__footer">
        <span className={evidence.evidence_type === "LOG" ? "is-untrusted" : ""}>
          <ShieldQuestion size={13} aria-hidden="true" /> {presentation.trust}
        </span>
        <CopyableId label="Fingerprint" value={evidence.fingerprint.slice(0, 12)} />
        <button className="text-button" type="button" onClick={() => onInspect(evidence)}>
          Inspect raw detail
        </button>
      </div>
    </article>
  );
}

type ApprovalDecision = "approve" | "reject";

export function ApprovalDecisionPanel({
  approval,
  incident,
  workflow,
  reason,
  pending,
  onReasonChange,
  onDecide,
}: {
  approval: ApprovalRequest;
  incident: Incident;
  workflow?: WorkflowRun;
  reason: string;
  pending: boolean;
  onReasonChange: (reason: string) => void;
  onDecide: (id: string, decision: ApprovalDecision) => void;
}) {
  const [confirming, setConfirming] = useState<ApprovalDecision | null>(null);
  const action = workflow?.state_references.action_type ?? "structured remediation";
  const risk = workflow?.state_references.risk_level ?? "Policy assessed";
  const diagnosis = [...incident.diagnoses].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  )[0];
  return (
    <article className="approval-decision-panel">
      <header>
        <div>
          <span className="section-eyebrow">Governed decision</span>
          <h3>Approval decision</h3>
        </div>
        <StatusBadge status={approval.status} domain="approval" />
      </header>
      <dl className="approval-decision-panel__facts">
        <Fact label="Action" value={action} mono />
        <Fact label="Target" value={incident.service} />
        <Fact label="Environment" value={incident.environment} />
        <Fact label="Risk" value={risk} />
        <Fact label="Why approval required" value="Infrastructure change is policy governed" />
        <Fact
          label="Evidence basis"
          value={`${diagnosis?.evidence_ids.length ?? 0} current evidence reference(s)`}
        />
        <Fact label="Requested at" value={formatIncidentDate(approval.requested_at)} />
        <Fact
          label="Approver"
          value={approval.approver_display_name ?? "Awaiting an authorized operator"}
        />
      </dl>
      <CopyableId label="Action fingerprint" value={approval.action_fingerprint} />
      {approval.status === "PENDING" ? (
        <div className="approval-decision-panel__decision">
          <label>
            <span>Decision reason</span>
            <textarea
              value={reason}
              maxLength={1000}
              onChange={(event) => onReasonChange(event.target.value)}
              placeholder="Record the evidence-based reason for this decision"
            />
          </label>
          <div>
            <button
              className="button button--primary"
              type="button"
              disabled={!reason.trim() || pending}
              onClick={() => setConfirming("approve")}
            >
              <CheckCircle2 size={15} aria-hidden="true" /> Approve
            </button>
            <button
              className="button button--danger"
              type="button"
              disabled={!reason.trim() || pending}
              onClick={() => setConfirming("reject")}
            >
              <XCircle size={15} aria-hidden="true" /> Reject
            </button>
          </div>
        </div>
      ) : (
        <p className="approval-decision-panel__resolution">
          <ShieldCheck size={15} aria-hidden="true" />
          {approval.reason ?? "Decision recorded"} · {formatIncidentDate(approval.resolved_at)}
        </p>
      )}
      <ApprovalConfirmDialog
        decision={confirming}
        action={action}
        target={incident.service}
        environment={incident.environment}
        risk={risk}
        pending={pending}
        onClose={() => setConfirming(null)}
        onConfirm={() => {
          if (!confirming) return;
          onDecide(approval.id, confirming);
          setConfirming(null);
        }}
      />
    </article>
  );
}

function ApprovalConfirmDialog({
  decision,
  action,
  target,
  environment,
  risk,
  pending,
  onClose,
  onConfirm,
}: {
  decision: ApprovalDecision | null;
  action: string;
  target: string;
  environment: string;
  risk: string;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!decision) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
        ),
      );
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previousFocus.current?.focus();
    };
  }, [decision, onClose, pending]);
  if (!decision) return null;
  const approving = decision === "approve";
  return (
    <div className="confirm-dialog-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <button
          className="icon-button confirm-dialog__close"
          aria-label="Close approval confirmation"
          onClick={onClose}
          disabled={pending}
        >
          <X size={18} aria-hidden="true" />
        </button>
        <span className="section-eyebrow">Confirm governed decision</span>
        <h2 id={titleId}>{approving ? "Approve action" : "Reject action"}</h2>
        <p>
          {approving
            ? "The workflow may resume, but policy and execution controls remain enforced."
            : "This action request will not execute. The incident remains available for investigation."}
        </p>
        <dl>
          <Fact label="What will happen" value={approving ? action : "Execution will be blocked"} />
          <Fact label="Target" value={target} />
          <Fact label="Environment" value={environment} />
          <Fact label="Risk" value={risk} />
        </dl>
        <div className="confirm-dialog__actions">
          <button ref={cancelRef} className="button button--secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className={approving ? "button button--primary" : "button button--danger"}
            onClick={onConfirm}
            disabled={pending}
          >
            {approving ? (
              <CheckCircle2 size={15} aria-hidden="true" />
            ) : (
              <XCircle size={15} aria-hidden="true" />
            )}
            Confirm {approving ? "approval" : "rejection"}
          </button>
        </div>
      </section>
    </div>
  );
}

export function ExecutionPanel({
  execution,
  onInspect,
}: {
  execution: ExecutionRecord;
  onInspect: (execution: ExecutionRecord) => void;
}) {
  const started = execution.started_at ? Date.parse(execution.started_at) : null;
  const finished = execution.finished_at ? Date.parse(execution.finished_at) : null;
  const duration = started && finished ? Math.max(0, finished - started) : null;
  const indeterminate = ["UNKNOWN", "RECONCILIATION_REQUIRED"].includes(execution.status);
  return (
    <article className={`execution-panel ${indeterminate ? "is-indeterminate" : ""}`}>
      <header>
        <div>
          <span className="section-eyebrow">Governed execution</span>
          <h3>
            {execution.backend_type} / <code>{execution.backend_profile}</code>
          </h3>
        </div>
        <button className="text-button" type="button" onClick={() => onInspect(execution)}>
          Technical detail
        </button>
      </header>
      <div className="execution-panel__outcomes">
        <section>
          <span>Execution</span>
          <StatusBadge status={execution.status} domain="execution" />
          <small>Provider-side action result</small>
        </section>
        <section id="verification">
          <span>Verification</span>
          <StatusBadge status={execution.verification_status ?? "PENDING"} domain="verification" />
          <small>Post-action incident health</small>
        </section>
      </div>
      {indeterminate ? (
        <div className="reconciliation-notice" role="note">
          <AlertTriangle size={18} aria-hidden="true" />
          <div>
            <strong>Execution outcome is indeterminate.</strong>
            <span>Automatic redispatch is disabled.</span>
            <small>
              Next safe action: reconcile provider state before any new execution attempt.
            </small>
          </div>
        </div>
      ) : null}
      <dl className="execution-panel__facts">
        <Fact label="Backend" value={execution.backend_type} />
        <Fact label="Profile" value={execution.backend_profile} mono />
        <Fact label="Submitted" value={formatIncidentDate(execution.submitted_at)} />
        <Fact label="Started" value={formatIncidentDate(execution.started_at)} />
        <Fact
          label="Duration"
          value={
            duration === null ? "In progress / not recorded" : `${Math.round(duration / 1000)}s`
          }
        />
        <Fact
          label="Provider reference"
          value={execution.provider_execution_id ?? "Not recorded"}
          mono
        />
        <Fact label="Reconciliation" value={formatIncidentDate(execution.last_reconciled_at)} />
        <Fact label="Attempt" value={String(execution.attempt)} />
      </dl>
    </article>
  );
}

const timelinePresentation: Record<string, { label: string; icon: typeof Activity }> = {
  INCIDENT: { label: "Incident", icon: AlertTriangle },
  EVIDENCE: { label: "Evidence collected", icon: ListChecks },
  HYPOTHESIS: { label: "Hypothesis recorded", icon: ShieldQuestion },
  DIAGNOSIS: { label: "Diagnosis produced", icon: Activity },
  ACTION: { label: "Action proposed", icon: ServerCog },
  APPROVAL: { label: "Approval decision", icon: ShieldCheck },
  VERIFICATION: { label: "Verification completed", icon: CheckCircle2 },
  WORKFLOW: { label: "Workflow state", icon: FileClock },
};

export function IncidentTimeline({
  items,
  onInspect,
}: {
  items: TimelineItem[];
  onInspect: (item: TimelineItem) => void;
}) {
  return (
    <ol className="operations-timeline">
      {items.map((item) => {
        const presentation = timelinePresentation[item.kind] ?? {
          label: item.kind,
          icon: ScrollText,
        };
        const Icon = presentation.icon;
        const actor = String(item.metadata.actor ?? item.metadata.started_by ?? "OpsPilot system");
        return (
          <li key={item.id}>
            <span className="operations-timeline__marker">
              <Icon size={15} aria-hidden="true" />
            </span>
            <div className="operations-timeline__content">
              <header>
                <span>{presentation.label}</span>
                <time dateTime={item.occurred_at}>{formatIncidentDate(item.occurred_at)}</time>
              </header>
              <strong>{item.summary}</strong>
              <small>
                {actor} · {item.event_type}
              </small>
            </div>
            {Object.keys(item.metadata).length ? (
              <button className="text-button" type="button" onClick={() => onInspect(item)}>
                Metadata
              </button>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function Fact({ label, value, mono = false }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : ""}>{value}</dd>
    </div>
  );
}
