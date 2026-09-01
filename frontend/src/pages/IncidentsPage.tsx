import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeft,
  BrainCircuit,
  CheckCircle2,
  History,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { approvalsApi, incidentsApi } from "../api";
import {
  ApprovalDecisionPanel,
  EvidenceCard,
  ExecutionPanel,
  formatIncidentDate,
  IncidentTimeline,
  LifecycleRail,
} from "../components/incidents/IncidentOperations";
import {
  CopyableId,
  DataTable,
  FilterBar,
  InlineNotice,
  PageHeader,
  PageSection,
  SearchInput,
  SeverityBadge,
  StatusBadge,
  TechnicalDetailDrawer,
} from "../components/OpsUI";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import { queryKeys } from "../query/queryKeys";
import type { ExecutionRecord, IncidentEvidence, TimelineItem } from "../types";

interface TechnicalDetail {
  title: string;
  subtitle?: string;
  identifiers?: Array<{ label: string; value: string | null | undefined }>;
  detail: unknown;
}

export function IncidentsPage({ environment }: { environment: string }) {
  const { incidentId } = useParams();
  if (incidentId) return <IncidentDetail incidentId={incidentId} />;
  return <IncidentList environment={environment} />;
}

function IncidentList({ environment }: { environment: string }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [environmentFilter, setEnvironmentFilter] = useState("ALL");
  const incidents = useQuery({
    queryKey: queryKeys.incidents(environment),
    queryFn: () => incidentsApi.list(environment),
  });
  const items = useMemo(() => incidents.data?.items ?? [], [incidents.data?.items]);
  const environments = [...new Set(items.map((item) => item.environment))].sort();
  const demoCandidate =
    items.find(
      (item) =>
        !["RESOLVED", "CLOSED"].includes(item.status) &&
        /service[- ]?down|unavailable|不可用/i.test(`${item.title} ${item.tags.join(" ")}`),
    ) ?? items.find((item) => !["RESOLVED", "CLOSED"].includes(item.status));
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return items.filter(
      (item) =>
        (!term ||
          `${item.title} ${item.service} ${item.environment} ${item.id}`
            .toLowerCase()
            .includes(term)) &&
        (severity === "ALL" || item.severity === severity) &&
        (status === "ALL" || item.status === status) &&
        (environmentFilter === "ALL" || item.environment === environmentFilter),
    );
  }, [environmentFilter, items, search, severity, status]);
  const hasFilters = Boolean(
    search || severity !== "ALL" || status !== "ALL" || environmentFilter !== "ALL",
  );
  const clearFilters = () => {
    setSearch("");
    setSeverity("ALL");
    setStatus("ALL");
    setEnvironmentFilter("ALL");
  };

  return (
    <div className="page-stack data-page incidents-page incident-list-page">
      <PageHeader
        title="Incidents"
        description="Prioritize active incidents and follow evidence, approval, execution, and verification without losing operational context."
        actions={
          <span className="page-header__status">
            <Activity size={16} aria-hidden="true" />
            {items.filter((item) => !["RESOLVED", "CLOSED"].includes(item.status)).length} open
          </span>
        }
      />
      {demoCandidate ? (
        <Link className="demo-path-banner" to={`/incidents/${demoCandidate.id}`}>
          <span>
            <ShieldCheck size={17} aria-hidden="true" />
            <strong>Portfolio demo path</strong>
          </span>
          <span>{demoCandidate.title}</span>
          <small>Evidence → Diagnosis → Approval → Execution → Verification</small>
        </Link>
      ) : null}
      <PageSection
        className="incidents-table-section"
        title="Incident queue"
        description={`Backend data for ${environment}; no synthetic priority score is applied.`}
      >
        <FilterBar ariaLabel="Search and filter incidents">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search title, service, environment, or ID"
            ariaLabel="Search incidents"
          />
          <label className="filter-control">
            <span>Severity</span>
            <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
              <option value="ALL">All severities</option>
              {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-control">
            <span>Status</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="ALL">All statuses</option>
              {[
                "OPEN",
                "INVESTIGATING",
                "MITIGATING",
                "VERIFYING",
                "RESOLVED",
                "CLOSED",
                "FAILED",
              ].map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-control">
            <span>Environment</span>
            <select
              value={environmentFilter}
              onChange={(event) => setEnvironmentFilter(event.target.value)}
            >
              <option value="ALL">All environments</option>
              {environments.map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <span className="filter-bar__count">{filtered.length} incidents</span>
          {hasFilters ? (
            <button className="text-button" type="button" onClick={clearFilters}>
              <RotateCcw size={14} aria-hidden="true" /> Clear filters
            </button>
          ) : null}
        </FilterBar>
        {incidents.isLoading ? (
          <LoadingState variant="table" />
        ) : incidents.error ? (
          <ErrorState error={incidents.error} onRetry={() => void incidents.refetch()} />
        ) : !items.length ? (
          <EmptyState
            title="No incidents"
            message="Incidents created through the API appear here."
          />
        ) : !filtered.length ? (
          <EmptyState
            title="No matching incidents"
            message="Change or clear the search and filters to see the current queue."
          />
        ) : (
          <DataTable ariaLabel="Incident queue">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Status</th>
                <th>Service</th>
                <th>Environment</th>
                <th>Title</th>
                <th>Evidence</th>
                <th>Action</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr
                  key={item.id}
                  className={item.id === demoCandidate?.id ? "is-demo-incident" : ""}
                  tabIndex={0}
                  onClick={() => navigate(`/incidents/${item.id}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") navigate(`/incidents/${item.id}`);
                  }}
                >
                  <td>
                    <SeverityBadge severity={item.severity} />
                  </td>
                  <td>
                    <StatusBadge status={item.status} domain="incident" />
                  </td>
                  <td>{item.service}</td>
                  <td>
                    <span className="environment-identity">{item.environment}</span>
                  </td>
                  <td className="incident-title-cell">
                    <Link
                      className="entity-link"
                      to={`/incidents/${item.id}`}
                      onClick={(event) => event.stopPropagation()}
                    >
                      {item.title}
                    </Link>
                    <small className="mono">{item.id.slice(0, 8)}</small>
                  </td>
                  <td>{item.evidence.length}</td>
                  <td>{item.actions.length ? `${item.actions.length} linked` : "Not proposed"}</td>
                  <td>{formatIncidentDate(item.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </PageSection>
    </div>
  );
}

function IncidentDetail({ incidentId }: { incidentId: string }) {
  const queryClient = useQueryClient();
  const [approvalReason, setApprovalReason] = useState("");
  const [technicalDetail, setTechnicalDetail] = useState<TechnicalDetail | null>(null);
  const incident = useQuery({
    queryKey: queryKeys.incident(incidentId),
    queryFn: () => incidentsApi.detail(incidentId),
  });
  const timeline = useQuery({
    queryKey: queryKeys.incidentTimeline(incidentId),
    queryFn: () => incidentsApi.timeline(incidentId),
  });
  const workflows = useQuery({
    queryKey: queryKeys.incidentWorkflows(incidentId),
    queryFn: () => incidentsApi.workflows(incidentId),
  });
  const related = useQuery({
    queryKey: queryKeys.incidentRelated(incidentId),
    queryFn: () => incidentsApi.related(incidentId),
  });
  const executions = useQuery({
    queryKey: queryKeys.incidentExecutions(incidentId),
    queryFn: () => incidentsApi.executions(incidentId),
  });
  const approvals = useQuery({
    queryKey: queryKeys.incidentApprovals(incidentId),
    queryFn: () => approvalsApi.list(incidentId),
  });
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" }) =>
      approvalsApi[decision](id, approvalReason),
    onSuccess: async () => {
      setApprovalReason("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.incidentApprovals(incidentId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.incidentWorkflows(incidentId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.incidentExecutions(incidentId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.incident(incidentId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.incidentTimeline(incidentId) }),
      ]);
    },
  });
  useEffect(() => {
    if (!incident.data || !window.location.hash) return;
    window.requestAnimationFrame(() =>
      document.querySelector<HTMLElement>(window.location.hash)?.scrollIntoView({ block: "start" }),
    );
  }, [incident.data]);

  if (incident.isLoading) return <LoadingState label="Loading incident" />;
  if (incident.error)
    return <ErrorState error={incident.error} onRetry={() => void incident.refetch()} />;
  const item = incident.data!;
  const workflowItems = workflows.data ?? [];
  const approvalItems = approvals.data ?? [];
  const executionItems = executions.data ?? [];
  const latestWorkflow = workflowItems[0];

  const inspectEvidence = (evidence: IncidentEvidence) =>
    setTechnicalDetail({
      title: `${evidence.evidence_type} evidence detail`,
      subtitle: "External observation; content is not an instruction to OpsPilot.",
      identifiers: [
        { label: "Evidence ID", value: evidence.id },
        { label: "Fingerprint", value: evidence.fingerprint },
      ],
      detail: {
        evidence_type: evidence.evidence_type,
        source: evidence.source,
        source_reference: evidence.source_reference,
        observed_at: evidence.observed_at,
        collected_at: evidence.collected_at,
        collector: evidence.collector,
        excerpt: evidence.excerpt,
        metadata: evidence.metadata,
      },
    });
  const inspectExecution = (execution: ExecutionRecord) =>
    setTechnicalDetail({
      title: "Execution technical detail",
      subtitle: "Provider, reconciliation, trace, and artifact identifiers.",
      identifiers: [
        { label: "Execution ID", value: execution.id },
        { label: "Provider reference", value: execution.provider_execution_id },
        { label: "Trace ID", value: execution.trace_id },
      ],
      detail: execution,
    });
  const inspectTimeline = (entry: TimelineItem) =>
    setTechnicalDetail({
      title: "Timeline metadata",
      subtitle: `${entry.kind} · ${formatIncidentDate(entry.occurred_at)}`,
      identifiers: [
        { label: "Event ID", value: entry.id },
        { label: "Reference ID", value: entry.reference_id },
      ],
      detail: entry.metadata,
    });

  return (
    <div className="page-stack data-page incidents-page incident-detail-page">
      <PageHeader
        title={item.title}
        description={item.summary}
        actions={
          <Link className="button button--secondary" to="/incidents">
            <ArrowLeft size={15} aria-hidden="true" /> Back to incidents
          </Link>
        }
      />
      <section className="incident-hero" aria-label="Incident identity">
        <div className="incident-hero__status">
          <SeverityBadge severity={item.severity} />
          <StatusBadge status={item.status} domain="incident" />
          <span className="workflow-state">
            <Activity size={14} aria-hidden="true" />
            Workflow {latestWorkflow?.status ?? "NOT STARTED"}
          </span>
        </div>
        <dl>
          <IncidentFact label="Service" value={item.service} />
          <IncidentFact label="Environment" value={item.environment} emphasis />
          <IncidentFact label="Created" value={formatIncidentDate(item.created_at)} />
          <IncidentFact label="Updated" value={formatIncidentDate(item.updated_at)} />
          <IncidentFact label="Source" value={item.source} />
          <IncidentFact label="Owner" value={item.created_by} />
        </dl>
        <CopyableId label="Incident ID" value={item.id} />
      </section>

      <div className="incident-detail-layout">
        <aside className="incident-detail-layout__rail">
          <LifecycleRail
            incident={item}
            workflows={workflowItems}
            approvals={approvalItems}
            executions={executionItems}
          />
        </aside>
        <div className="incident-detail-layout__content">
          <PageSection id="overview" className="incident-section" title="Overview">
            <div className="incident-overview-summary">
              <div>
                <span className="section-eyebrow">Operational summary</span>
                <p>{item.summary}</p>
              </div>
              <dl>
                <IncidentFact label="Version" value={`v${item.version}`} />
                <IncidentFact label="Evidence" value={String(item.evidence.length)} />
                <IncidentFact label="Diagnoses" value={String(item.diagnoses.length)} />
                <IncidentFact label="Actions" value={String(item.actions.length)} />
              </dl>
            </div>
          </PageSection>

          <PageSection
            id="evidence"
            className="incident-section"
            title="Evidence"
            description="Current incident observations. Raw technical content is collapsed and never treated as trusted instruction."
          >
            {item.evidence.length ? (
              <div className="evidence-grid">
                {item.evidence.map((evidence) => (
                  <EvidenceCard key={evidence.id} evidence={evidence} onInspect={inspectEvidence} />
                ))}
              </div>
            ) : (
              <EmptyState title="No current evidence" message="Collected Evidence appears here." />
            )}
          </PageSection>

          <PageSection
            id="investigation"
            className="incident-section"
            title="Investigation / Hypotheses"
            description="Grounded Investigator progress; private model internals are not exposed."
          >
            <div className="investigation-grid">
              <div>
                <span className="section-eyebrow">Hypotheses</span>
                {item.hypotheses.length ? (
                  <ul className="hypothesis-list">
                    {item.hypotheses.map((hypothesis) => (
                      <li key={hypothesis.id}>
                        <BrainCircuit size={16} aria-hidden="true" />
                        <span>
                          <strong>{hypothesis.statement}</strong>
                          <small>
                            {hypothesis.status} · confidence{" "}
                            {Math.round(hypothesis.confidence * 100)}%
                          </small>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted-copy">No hypotheses recorded.</p>
                )}
              </div>
              <div>
                <span className="section-eyebrow">Workflow</span>
                {workflows.isLoading ? (
                  <LoadingState variant="cards" />
                ) : workflows.error ? (
                  <ErrorState error={workflows.error} onRetry={() => void workflows.refetch()} />
                ) : workflowItems.length ? (
                  <div className="workflow-run-list">
                    {workflowItems.map((workflow) => (
                      <article key={workflow.id}>
                        <StatusBadge status={workflow.status} />
                        <strong>{workflow.current_node ?? "queued"}</strong>
                        <small>
                          Investigator{" "}
                          {workflow.state_references.investigator_mode ?? "deterministic"}
                          {workflow.state_references.model
                            ? ` / ${workflow.state_references.model}`
                            : ""}
                        </small>
                        <span>
                          {workflow.state_references.decision_summary ??
                            "Awaiting grounded decision"}
                        </span>
                        {workflow.state_references.uncertainty ? (
                          <small>Uncertainty: {workflow.state_references.uncertainty}</small>
                        ) : null}
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="No workflow"
                    message="Start the incident workflow through the API."
                  />
                )}
              </div>
            </div>
          </PageSection>

          <PageSection
            id="diagnosis"
            className="incident-section diagnosis-section"
            title="Diagnosis"
            description="Diagnosis is grounded only in Current Evidence; Historical Knowledge is displayed separately."
          >
            <div className="context-boundary-label is-current">
              <CheckCircle2 size={15} aria-hidden="true" /> Current Evidence
            </div>
            {item.diagnoses.length ? (
              <div className="diagnosis-list">
                {item.diagnoses.map((diagnosis) => (
                  <article key={diagnosis.id}>
                    <header>
                      <strong>{diagnosis.root_cause}</strong>
                      <span>{Math.round(diagnosis.confidence * 100)}% confidence</span>
                    </header>
                    <div>
                      <span className="section-eyebrow">Supporting evidence</span>
                      <div className="evidence-reference-list">
                        {diagnosis.evidence_ids.map((id) => (
                          <a href={`#evidence-${id}`} key={id} className="mono">
                            {id.slice(0, 12)}
                          </a>
                        ))}
                      </div>
                    </div>
                    <div>
                      <span className="section-eyebrow">Contributing factors</span>
                      <ul>
                        {diagnosis.contributing_factors.length ? (
                          diagnosis.contributing_factors.map((factor) => (
                            <li key={factor}>{factor}</li>
                          ))
                        ) : (
                          <li>None recorded</li>
                        )}
                      </ul>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No diagnosis"
                message="A grounded root cause appears here when available."
              />
            )}
          </PageSection>

          <PageSection
            id="knowledge"
            className="incident-section knowledge-section"
            title="Historical Context / Related Incidents"
            description="Historical Knowledge · Not current evidence · Cannot authorize an action."
          >
            <div className="context-boundary-label is-historical">
              <History size={15} aria-hidden="true" /> Historical context · Not current evidence
            </div>
            {related.isLoading ? (
              <LoadingState variant="cards" />
            ) : related.error ? (
              <ErrorState error={related.error} onRetry={() => void related.refetch()} />
            ) : related.data?.length ? (
              <div className="knowledge-list">
                {related.data.map((memory, rank) => (
                  <article key={memory.knowledge_id}>
                    <header>
                      <span>Retrieval rank {rank + 1}</span>
                      <strong>{memory.title}</strong>
                      <small>Similarity {memory.retrieval_score.toFixed(3)}</small>
                    </header>
                    <dl>
                      <IncidentFact label="Service" value={memory.service} />
                      <IncidentFact label="Environment" value={memory.environment} />
                      <IncidentFact
                        label="Resolved"
                        value={formatIncidentDate(memory.resolved_at)}
                      />
                    </dl>
                    <p>
                      <strong>Root cause:</strong> {memory.root_cause}
                    </p>
                    <p>
                      <strong>Resolution:</strong> {memory.remediation.join(", ") || "Not recorded"}
                    </p>
                    <a href={memory.source_reference}>Open source incident</a>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No historical context"
                message="Related resolved incidents appear here when retrieval is available."
              />
            )}
          </PageSection>

          <PageSection
            id="action-proposal"
            className="incident-section action-proposal-section"
            title="Action Proposal / Risk Assessment"
            description="Operator-visible proposal produced by the governed workflow."
          >
            {latestWorkflow?.state_references.action_type ? (
              <div className="action-proposal">
                <ShieldCheck size={20} aria-hidden="true" />
                <dl>
                  <IncidentFact
                    label="Action"
                    value={latestWorkflow.state_references.action_type}
                  />
                  <IncidentFact label="Target" value={item.service} />
                  <IncidentFact label="Environment" value={item.environment} emphasis />
                  <IncidentFact
                    label="Risk"
                    value={latestWorkflow.state_references.risk_level ?? "Not recorded"}
                  />
                </dl>
                <p>
                  {latestWorkflow.state_references.decision_summary ??
                    "Structured action proposed from current evidence."}
                </p>
                {latestWorkflow.state_references.action_fingerprint ? (
                  <CopyableId
                    label="Fingerprint"
                    value={latestWorkflow.state_references.action_fingerprint}
                  />
                ) : null}
              </div>
            ) : (
              <EmptyState
                title="No action proposal"
                message="Investigation can complete without proposing remediation."
              />
            )}
          </PageSection>

          <PageSection
            id="approval"
            className="incident-section approval-section"
            title="Approval"
            description="Human approval is a durable policy boundary and never bypasses execution controls."
          >
            {approvals.isLoading ? (
              <LoadingState variant="cards" />
            ) : approvals.error ? (
              <ErrorState error={approvals.error} onRetry={() => void approvals.refetch()} />
            ) : approvalItems.length ? (
              <div className="approval-panel-list">
                {approvalItems.map((approval) => (
                  <ApprovalDecisionPanel
                    key={approval.id}
                    approval={approval}
                    incident={item}
                    workflow={workflowItems.find(
                      (candidate) => candidate.id === approval.workflow_run_id,
                    )}
                    reason={approvalReason}
                    pending={decide.isPending}
                    onReasonChange={setApprovalReason}
                    onDecide={(id, decision) => decide.mutate({ id, decision })}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No approval request"
                message="The workflow pauses here only when policy requires human approval."
              />
            )}
            {decide.error ? (
              <InlineNotice title="Decision not recorded" tone="danger">
                {decide.error instanceof Error
                  ? decide.error.message
                  : "Retry after checking authorization."}
              </InlineNotice>
            ) : null}
          </PageSection>

          <PageSection
            id="execution"
            className="incident-section execution-section"
            title="Execution / Verification"
            description="Backend completion, reconciliation, and incident verification remain independent states."
          >
            {executions.isLoading ? (
              <LoadingState variant="cards" />
            ) : executions.error ? (
              <ErrorState error={executions.error} onRetry={() => void executions.refetch()} />
            ) : executionItems.length ? (
              <div className="execution-panel-list">
                {executionItems.map((execution) => (
                  <ExecutionPanel
                    key={execution.id}
                    execution={execution}
                    onInspect={inspectExecution}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No execution"
                message="Approved governed actions appear here after submission."
              />
            )}
          </PageSection>

          <PageSection
            id="timeline"
            className="incident-section timeline-section"
            title="Timeline / Audit"
            description="Evidence, diagnosis, policy, approval, execution, verification, and resolution in event order."
          >
            {timeline.isLoading ? (
              <LoadingState variant="table" />
            ) : timeline.error ? (
              <ErrorState error={timeline.error} onRetry={() => void timeline.refetch()} />
            ) : timeline.data?.length ? (
              <IncidentTimeline items={timeline.data} onInspect={inspectTimeline} />
            ) : (
              <EmptyState
                title="No timeline events"
                message="Incident events appear here as they are recorded."
              />
            )}
          </PageSection>
        </div>
      </div>
      <TechnicalDetailDrawer
        open={Boolean(technicalDetail)}
        title={technicalDetail?.title ?? "Technical detail"}
        subtitle={technicalDetail?.subtitle}
        identifiers={technicalDetail?.identifiers}
        detail={technicalDetail?.detail}
        onClose={() => setTechnicalDetail(null)}
      />
    </div>
  );
}

function IncidentFact({
  label,
  value,
  emphasis = false,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className={emphasis ? "is-emphasis" : ""}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
