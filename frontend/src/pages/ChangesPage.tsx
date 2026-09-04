import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  GitCommitHorizontal,
  GitMerge,
  GitPullRequest,
  RefreshCw,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { changesApi } from "../api";
import {
  CopyableId,
  DataTable,
  PageHeader,
  PageSection,
  StatusBadge,
  TechnicalDetailDrawer,
} from "../components/OpsUI";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import { queryKeys } from "../query/queryKeys";
import type { ChangeStatus } from "../types";

const lifecycle = ["Propose", "Policy", "Approve", "PR", "Review", "Merge", "Sync", "Verify"];
const statusStep: Record<ChangeStatus, number> = {
  PROPOSED: 0,
  POLICY_APPROVED: 1,
  WAITING_APPROVAL: 2,
  APPROVED: 2,
  PLANNED: 2,
  VALIDATED: 2,
  QUEUED: 2,
  BRANCH_CREATED: 3,
  COMMITTED: 3,
  PR_CREATED: 3,
  WAITING_REVIEW: 4,
  APPROVED_FOR_MERGE: 5,
  MERGED: 6,
  RECONCILING: 6,
  SYNCED: 6,
  HEALTHY: 7,
  VERIFIED: 7,
  RESOLVED: 8,
  REJECTED: 2,
  FAILED: 7,
  UNKNOWN: 3,
  RECONCILIATION_REQUIRED: 3,
};

export function ChangesPage({ environment }: { environment: string }) {
  const { changeId } = useParams();
  return changeId ? <ChangeDetail changeId={changeId} /> : <ChangeList environment={environment} />;
}

function ChangeList({ environment }: { environment: string }) {
  const changes = useQuery({ queryKey: queryKeys.changes, queryFn: () => changesApi.list() });
  const items = useMemo(
    () => (changes.data?.items ?? []).filter((item) => item.profile_id.includes(environment)),
    [changes.data?.items, environment],
  );
  return (
    <div className="page-stack data-page changes-page">
      <PageHeader
        title="GitOps Changes"
        description="Desired-state changes pass through OpsPilot approval and a separate Git review before pull-based reconciliation."
      />
      <PageSection
        title="Change queue"
        description="PR created does not mean deployed; merged does not mean synced or verified."
      >
        {changes.isLoading ? (
          <LoadingState variant="table" />
        ) : changes.error ? (
          <ErrorState error={changes.error} onRetry={() => void changes.refetch()} />
        ) : !items.length ? (
          <EmptyState title="No GitOps changes" message="Governed semantic changes appear here." />
        ) : (
          <DataTable ariaLabel="GitOps change queue">
            <thead>
              <tr>
                <th>Status</th>
                <th>Change</th>
                <th>Type</th>
                <th>Profile</th>
                <th>PR</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <StatusBadge status={item.status} domain="change" />
                  </td>
                  <td>
                    <Link to={`/changes/${item.id}`}>{item.id.slice(0, 8)}</Link>
                  </td>
                  <td>{item.change_type}</td>
                  <td>{item.profile_id}</td>
                  <td>{item.pull_request_id ? `#${item.pull_request_id}` : "Not created"}</td>
                  <td>{new Date(item.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </PageSection>
    </div>
  );
}

function ChangeDetail({ changeId }: { changeId: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [rawDiffOpen, setRawDiffOpen] = useState(false);
  const [confirming, setConfirming] = useState<"approve" | "reject" | null>(null);
  const change = useQuery({
    queryKey: queryKeys.change(changeId),
    queryFn: () => changesApi.detail(changeId),
  });
  const timeline = useQuery({
    queryKey: queryKeys.changeTimeline(changeId),
    queryFn: () => changesApi.timeline(changeId),
  });
  const previewEnabled = Boolean(
    change.data && statusStep[change.data.status] >= 2 && change.data.status !== "WAITING_APPROVAL",
  );
  const preview = useQuery({
    queryKey: queryKeys.changePreview(changeId),
    queryFn: () => changesApi.preview(changeId),
    enabled: previewEnabled,
  });
  const decide = useMutation({
    mutationFn: (decision: "approve" | "reject") => changesApi[decision](changeId, reason),
    onSuccess: async () => {
      setReason("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.change(changeId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.changeTimeline(changeId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.changePreview(changeId) }),
      ]);
    },
  });
  const reconcile = useMutation({
    mutationFn: () => changesApi.reconcile(changeId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.change(changeId) }),
  });
  if (change.isLoading) return <LoadingState label="Loading change" />;
  if (change.error)
    return <ErrorState error={change.error} onRetry={() => void change.refetch()} />;
  const item = change.data!;
  const currentStep = statusStep[item.status];
  return (
    <div className="page-stack data-page changes-page change-detail-page">
      <PageHeader
        title={`${item.change_type} · ${item.profile_id}`}
        description="A governed desired-state mutation with two independent human gates."
        actions={
          <Link className="button button--secondary" to="/changes">
            <ArrowLeft size={15} /> Back to changes
          </Link>
        }
      />
      {item.status === "UNKNOWN" || item.status === "RECONCILIATION_REQUIRED" ? (
        <div className="change-uncertain" role="alert">
          <AlertTriangle size={19} />
          <div>
            <strong>PR creation outcome is indeterminate</strong>
            <p>Automatic duplicate creation is disabled. Reconciliation is required.</p>
          </div>
          <button className="button button--secondary" onClick={() => reconcile.mutate()}>
            <RefreshCw size={15} /> Reconcile
          </button>
        </div>
      ) : null}
      <ol className="change-lifecycle" aria-label="Change lifecycle">
        {lifecycle.map((label, index) => (
          <li
            className={
              index < currentStep ? "is-complete" : index === currentStep ? "is-current" : ""
            }
            key={label}
          >
            <span>{index < currentStep ? <CheckCircle2 size={14} /> : index + 1}</span>
            <strong>{label}</strong>
          </li>
        ))}
      </ol>
      <section className="change-identity">
        <CopyableId label="Change ID" value={item.id} />
        <dl>
          <Fact label="Incident" value={item.incident_id} />
          <Fact label="Environment profile" value={item.profile_id} />
          <Fact label="Risk" value="HIGH" />
          <Fact label="Status" value={item.status} />
          <Fact label="Approver" value={item.approval_actor ?? "Waiting"} />
          <Fact label="Decision reason" value={item.approval_reason ?? "Waiting"} />
        </dl>
      </section>
      <div className="change-gates">
        <PageSection title="OpsPilot Approval" description="Gate A authorizes PR creation only.">
          <div className="gate-state">
            <ShieldCheck size={20} />
            <StatusBadge status={item.approval_id ? "APPROVED" : "WAITING"} />
          </div>
          {item.status === "WAITING_APPROVAL" ? (
            <div className="change-decision">
              <label>
                Decision reason
                <textarea value={reason} onChange={(event) => setReason(event.target.value)} />
              </label>
              <div>
                <button
                  disabled={reason.trim().length < 3}
                  onClick={() => setConfirming("approve")}
                >
                  Approve PR creation
                </button>
                <button
                  className="button--danger"
                  disabled={reason.trim().length < 3}
                  onClick={() => setConfirming("reject")}
                >
                  <XCircle size={15} aria-hidden="true" /> Reject
                </button>
              </div>
              {decide.error ? <p role="alert">{decide.error.message}</p> : null}
            </div>
          ) : null}
        </PageSection>
        <PageSection
          title="Git Review"
          description="Gate B independently authorizes merge on the protected branch."
        >
          <div className="gate-state">
            <GitPullRequest size={20} />
            <StatusBadge status={item.review_state ?? "WAITING"} />
          </div>
          <p className="boundary-note">
            OpsPilot cannot review, approve, or merge its own pull request.
          </p>
        </PageSection>
      </div>
      <PageSection
        title="Semantic Diff"
        description="Policy-readable desired-state change; raw Git diff remains technical detail."
      >
        {preview.data ? (
          <div className="semantic-diff">
            <header>
              <strong>{preview.data.resource}</strong>
              <span>{preview.data.field}</span>
            </header>
            <div>
              <section>
                <small>Before</small>
                <code>{preview.data.before}</code>
              </section>
              <section>
                <small>After</small>
                <code>{preview.data.after}</code>
              </section>
            </div>
            <dl>
              <Fact label="Blast Radius" value={String(preview.data.blast_radius)} />
              <Fact label="Artifact" value={preview.data.artifact ?? "N/A"} />
              <Fact label="Verification Plan" value={preview.data.verification_plan.profile_ref} />
            </dl>
            <button className="text-button" onClick={() => setRawDiffOpen(true)}>
              View technical Git diff
            </button>
          </div>
        ) : (
          <p>
            Semantic preview becomes available after OpsPilot approval and deterministic planning.
          </p>
        )}
      </PageSection>
      <div className="change-gitops-grid">
        <PageSection title="Git Revision">
          <Revision
            icon={<GitCommitHorizontal size={18} />}
            label="Source"
            value={item.source_revision}
          />
          <Revision
            icon={<GitCommitHorizontal size={18} />}
            label="Commit"
            value={item.commit_sha}
          />
          <Revision icon={<GitMerge size={18} />} label="Merged" value={item.merged_revision} />
        </PageSection>
        <PageSection title="GitOps Reconciliation">
          <Fact label="Application" value={item.gitops_application_ref} />
          <Fact label="Sync" value={item.sync_status ?? "WAITING"} />
          <Fact label="Health" value={item.health_status ?? "WAITING"} />
          <Fact label="Verification" value={item.verification_status ?? "WAITING"} />
        </PageSection>
      </div>
      <PageSection
        title="Change Timeline"
        description="Durable policy, approval, Git, reconciliation, and verification events."
      >
        {timeline.data?.length ? (
          <ol className="change-timeline">
            {timeline.data.map((event) => (
              <li key={event.id}>
                <span />
                <div>
                  <strong>{event.event_type}</strong>
                  <p>{event.summary}</p>
                  <time>{new Date(event.occurred_at).toLocaleString()}</time>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p>No timeline events are available.</p>
        )}
      </PageSection>
      <TechnicalDetailDrawer
        open={rawDiffOpen}
        title="Raw Git diff"
        subtitle="Read-only technical detail"
        identifiers={[
          { label: "Change ID", value: item.id },
          { label: "Commit", value: item.commit_sha },
        ]}
        onClose={() => setRawDiffOpen(false)}
      >
        <pre className="raw-git-diff">{preview.data?.raw_diff}</pre>
      </TechnicalDetailDrawer>
      <ChangeDecisionDialog
        decision={confirming}
        profile={item.profile_id}
        changeType={item.change_type}
        reason={reason}
        pending={decide.isPending}
        onClose={() => setConfirming(null)}
        onConfirm={() => {
          if (!confirming) return;
          decide.mutate(confirming, { onSuccess: () => setConfirming(null) });
        }}
      />
    </div>
  );
}

function ChangeDecisionDialog({
  decision,
  profile,
  changeType,
  reason,
  pending,
  onClose,
  onConfirm,
}: {
  decision: "approve" | "reject" | null;
  profile: string;
  changeType: string;
  reason: string;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!decision) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pending) onClose();
      if (event.key !== "Tab" || !dialogRef.current) return;
      const controls = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>("button:not(:disabled)"),
      );
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
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
          aria-label="Close change decision confirmation"
          disabled={pending}
          onClick={onClose}
        >
          <X size={18} aria-hidden="true" />
        </button>
        <span className="section-eyebrow">Gate A · HIGH risk</span>
        <h2 id={titleId}>{approving ? "Approve PR creation" : "Reject change"}</h2>
        <p>
          {approving
            ? "This authorizes OpsPilot to create a branch, commit, and pull request. It does not authorize Git review or merge."
            : "This permanently stops this proposal. A later attempt requires a new governed change."}
        </p>
        <dl>
          <Fact label="Change" value={changeType} />
          <Fact label="Environment profile" value={profile} />
          <Fact label="Risk" value="HIGH" />
          <Fact label="Reason" value={reason} />
        </dl>
        <div className="confirm-dialog__actions">
          <button
            ref={cancelRef}
            className="button button--secondary"
            disabled={pending}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className={approving ? "button button--primary" : "button button--danger"}
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? "Recording decision…" : approving ? "Approve PR creation" : "Reject change"}
          </button>
        </div>
      </section>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Revision({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | null;
}) {
  return (
    <div className="change-revision">
      {icon}
      <span>
        <small>{label}</small>
        <code>{value ?? "Waiting"}</code>
      </span>
    </div>
  );
}
