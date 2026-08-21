import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, Clock3 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { approvalsApi, incidentsApi } from "../api";
import { DataTable, PageHeader, PageSection, StatusBadge } from "../components/OpsUI";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import { queryKeys } from "../query/queryKeys";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function severityClass(severity: string): string {
  return `incident-severity incident-severity--${severity.toLowerCase()}`;
}

const evidenceLabels: Record<string, string> = {
  METRIC: "Metric",
  LOG: "Log",
  TICKET: "Ticket",
  SERVICE_STATUS: "Health",
};

function EvidenceReference({ value }: { value: string }) {
  if (/^https?:\/\//.test(value)) {
    return (
      <a href={value} rel="noreferrer">
        {value}
      </a>
    );
  }
  return <code className="mono">{value}</code>;
}

export function IncidentsPage({ environment }: { environment: string }) {
  const { incidentId } = useParams();
  if (incidentId) return <IncidentDetail incidentId={incidentId} />;
  return <IncidentList environment={environment} />;
}

function IncidentList({ environment }: { environment: string }) {
  const incidents = useQuery({
    queryKey: queryKeys.incidents(environment),
    queryFn: () => incidentsApi.list(environment),
  });
  return (
    <div className="page-stack data-page incidents-page">
      <PageHeader
        title="事件中心"
        description="查看从证据采集、诊断、治理动作到关闭的完整 Incident 生命周期。"
        actions={
          <span className="page-header__status">
            <Activity size={16} /> M1C Durable Incident Domain
          </span>
        }
      />
      <PageSection title="Incident 列表" description={`当前环境：${environment}`}>
        {incidents.isLoading ? (
          <LoadingState variant="table" />
        ) : incidents.error ? (
          <ErrorState error={incidents.error} onRetry={() => void incidents.refetch()} />
        ) : !incidents.data?.items.length ? (
          <EmptyState title="暂无 Incident" message="通过 Incident API 创建后会显示在这里。" />
        ) : (
          <DataTable ariaLabel="Incident 列表">
            <thead>
              <tr>
                <th>事件</th>
                <th>状态</th>
                <th>严重度</th>
                <th>服务</th>
                <th>环境</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              {incidents.data.items.map((incident) => (
                <tr key={incident.id}>
                  <td>
                    <Link className="entity-link" to={`/incidents/${incident.id}`}>
                      {incident.title}
                    </Link>
                    <small className="incident-id mono">{incident.id.slice(0, 8)}</small>
                  </td>
                  <td>
                    <StatusBadge status={incident.status} />
                  </td>
                  <td>
                    <span className={severityClass(incident.severity)}>{incident.severity}</span>
                  </td>
                  <td>{incident.service}</td>
                  <td>{incident.environment}</td>
                  <td>{formatDate(incident.created_at)}</td>
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
        queryClient.invalidateQueries({ queryKey: queryKeys.incident(incidentId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.incidentTimeline(incidentId) }),
      ]);
    },
  });
  if (incident.isLoading) return <LoadingState label="正在加载 Incident" />;
  if (incident.error)
    return <ErrorState error={incident.error} onRetry={() => void incident.refetch()} />;
  const item = incident.data!;
  return (
    <div className="page-stack data-page incidents-page">
      <PageHeader
        title={item.title}
        description={item.summary}
        actions={
          <Link className="button button--secondary" to="/incidents">
            <ArrowLeft size={15} /> 返回列表
          </Link>
        }
      />
      <div className="incident-overview-grid">
        <PageSection title="Overview">
          <dl className="incident-facts">
            <div>
              <dt>状态</dt>
              <dd>
                <StatusBadge status={item.status} />
              </dd>
            </div>
            <div>
              <dt>严重度</dt>
              <dd>
                <span className={severityClass(item.severity)}>{item.severity}</span>
              </dd>
            </div>
            <div>
              <dt>服务 / 环境</dt>
              <dd>
                {item.service} / {item.environment}
              </dd>
            </div>
            <div>
              <dt>来源 / 版本</dt>
              <dd>
                {item.source} / v{item.version}
              </dd>
            </div>
          </dl>
        </PageSection>
        <PageSection title="Diagnosis">
          {item.diagnoses.length ? (
            item.diagnoses.map((value) => (
              <article key={value.id} className="incident-card">
                <strong>{value.root_cause}</strong>
                <small>置信度 {Math.round(value.confidence * 100)}%</small>
                {value.evidence_ids.length ? (
                  <small>
                    Evidence: {value.evidence_ids.map((id) => (
                      <a key={id} href={`#evidence-${id}`} className="mono">
                        {id.slice(0, 8)}
                      </a>
                    ))}
                  </small>
                ) : null}
              </article>
            ))
          ) : (
            <EmptyState title="尚未记录诊断" message="诊断形成后会显示根因和影响因素。" />
          )}
        </PageSection>
      </div>
      <PageSection
        title="Collected Evidence"
        description="能力状态和原始数据由来源系统保留；这里只保存有界摘要与 provenance 引用。"
      >
        {item.evidence.length ? (
          <div className="incident-card-list">
            {item.evidence.map((value) => (
              <article key={value.id} id={`evidence-${value.id}`} className="incident-card">
                <span>
                  {evidenceLabels[value.evidence_type] ?? value.evidence_type} · {value.source}
                </span>
                <strong>{value.summary}</strong>
                <small>
                  观测 {formatDate(value.observed_at)} · 采集器 {value.collector}
                </small>
                <EvidenceReference value={value.source_reference} />
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无证据" message="Evidence API 写入后会显示在这里。" />
        )}
      </PageSection>
      <PageSection
        title="Workflow"
        description="LangGraph 编排进度；Incident 数据库仍是业务事实来源。"
      >
        {workflows.isLoading ? (
          <LoadingState variant="table" />
        ) : workflows.error ? (
          <ErrorState error={workflows.error} onRetry={() => void workflows.refetch()} />
        ) : !workflows.data?.length ? (
          <EmptyState title="暂无工作流" message="通过 Workflow API 启动后会显示在这里。" />
        ) : (
          <DataTable ariaLabel="Incident 工作流列表">
            <thead>
              <tr>
                <th>状态</th>
                <th>当前节点</th>
                <th>Investigator</th>
                <th>Grounded decision</th>
                <th>启动时间</th>
                <th>耗时</th>
                <th>最后错误</th>
              </tr>
            </thead>
            <tbody>
              {workflows.data.map((workflow) => {
                const started = workflow.started_at ? new Date(workflow.started_at) : null;
                const finished = workflow.finished_at ? new Date(workflow.finished_at) : null;
                const duration = started
                  ? Math.max(0, (finished ?? new Date()).getTime() - started.getTime())
                  : null;
                return (
                  <tr key={workflow.id}>
                    <td>
                      <StatusBadge status={workflow.status} />
                    </td>
                    <td className="mono">{workflow.current_node ?? "queued"}</td>
                    <td>
                      {workflow.state_references.investigator_mode ?? "deterministic"}
                      {workflow.state_references.model
                        ? ` / ${workflow.state_references.model}`
                        : ""}
                    </td>
                    <td>
                      {workflow.state_references.decision_summary ?? "—"}
                      {workflow.state_references.uncertainty ? (
                        <small>Uncertainty: {workflow.state_references.uncertainty}</small>
                      ) : null}
                      {workflow.state_references.investigation_evidence_ids?.map((id) => (
                        <a key={id} href={`#evidence-${id}`} className="mono">
                          {id.slice(0, 8)}
                        </a>
                      ))}
                    </td>
                    <td>{workflow.started_at ? formatDate(workflow.started_at) : "尚未启动"}</td>
                    <td>{duration === null ? "—" : `${Math.round(duration / 1000)}s`}</td>
                    <td>{workflow.last_error ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
        )}
      </PageSection>
      <PageSection
        title="Human Approval"
        description="人工决定是受策略约束的执行边界；批准不会跳过 Policy Engine。"
      >
        {approvals.isLoading ? (
          <LoadingState />
        ) : approvals.error ? (
          <ErrorState error={approvals.error} onRetry={() => void approvals.refetch()} />
        ) : !approvals.data?.length ? (
          <EmptyState title="暂无审批请求" message="需要变更基础设施时，工作流会在此安全暂停。" />
        ) : (
          <div className="incident-card-list">
            {approvals.data.map((approval) => {
              const workflow = workflows.data?.find(
                (candidate) => candidate.id === approval.workflow_run_id,
              );
              return (
                <article key={approval.id} className="incident-card approval-card">
                  <span>
                    Incident {item.id.slice(0, 8)} · <StatusBadge status={approval.status} />
                  </span>
                  <strong>
                    Action proposal: {workflow?.state_references.action_type ?? "structured action"}
                  </strong>
                  <small>
                    Risk: {workflow?.state_references.risk_level ?? "policy assessed"} · Fingerprint{" "}
                    <code>{approval.action_fingerprint.slice(0, 12)}</code>
                  </small>
                  <small>
                    Diagnosis: {item.diagnoses.at(-1)?.root_cause ?? "See diagnosis record"}
                  </small>
                  <small>
                    Evidence references: {item.diagnoses.at(-1)?.evidence_ids.length ?? 0} · Decision
                    summary: {workflow?.state_references.decision_summary ?? "Deterministic proposal"}
                  </small>
                  {approval.status === "PENDING" ? (
                    <div className="approval-actions">
                      <label>
                        决策理由
                        <textarea
                          value={approvalReason}
                          maxLength={1000}
                          onChange={(event) => setApprovalReason(event.target.value)}
                          placeholder="记录批准或拒绝的原因"
                        />
                      </label>
                      <div>
                        <button
                          className="button button--primary"
                          disabled={!approvalReason.trim() || decide.isPending}
                          onClick={() =>
                            decide.mutate({ id: approval.id, decision: "approve" })
                          }
                        >
                          Approve
                        </button>
                        <button
                          className="button button--danger"
                          disabled={!approvalReason.trim() || decide.isPending}
                          onClick={() => decide.mutate({ id: approval.id, decision: "reject" })}
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ) : (
                    <small>
                      {approval.approver_display_name} · {approval.reason} ·{" "}
                      {approval.resolved_at ? formatDate(approval.resolved_at) : "—"}
                    </small>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </PageSection>
      <div className="incident-overview-grid">
        <PageSection title="Hypotheses">
          {item.hypotheses.length ? (
            item.hypotheses.map((value) => (
              <article key={value.id} className="incident-card">
                <strong>{value.statement}</strong>
                <small>
                  {value.status} · {Math.round(value.confidence * 100)}%
                </small>
              </article>
            ))
          ) : (
            <p>暂无假设</p>
          )}
        </PageSection>
        <PageSection title="Actions">
          {item.actions.length ? (
            item.actions.map((value) => (
              <Link
                key={value.task_id}
                className="incident-card"
                to={`/tasks?task=${value.task_id}`}
              >
                <strong>任务 {value.task_id.slice(0, 8)}</strong>
                <small>{formatDate(value.created_at)}</small>
              </Link>
            ))
          ) : (
            <p>暂无关联治理动作</p>
          )}
        </PageSection>
      </div>
      <PageSection
        title="Timeline"
        description="Incident、证据、诊断和治理动作按发生时间统一排序。"
      >
        {timeline.isLoading ? (
          <LoadingState variant="table" />
        ) : timeline.error ? (
          <ErrorState error={timeline.error} onRetry={() => void timeline.refetch()} />
        ) : (
          <ol className="incident-timeline">
            {timeline.data?.map((value) => (
              <li key={value.id}>
                <Clock3 size={15} />
                <time>{formatDate(value.occurred_at)}</time>
                <span>{value.kind}</span>
                <strong>{value.summary}</strong>
              </li>
            ))}
          </ol>
        )}
      </PageSection>
    </div>
  );
}
