export interface ApiEnvelope<T> {
  request_id: string;
  data: T;
}

export interface Environment {
  id: string;
  name: string;
  code: string;
  enabled: boolean;
  description: string | null;
  environment_level: "DEVELOPMENT" | "TEST" | "PRODUCTION";
}

export interface Service {
  id: string;
  environment_id: string;
  name: string;
  service_type: string;
  is_middleware: boolean;
  description: string | null;
  enabled: boolean;
  host_count: number;
  current_status: string;
}

export interface Host {
  id: string;
  environment_id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  labels: Record<string, string>;
  last_status: string;
  service_count: number;
}

export interface Asset {
  id: string;
  name: string;
  environmentId: string;
  environmentName: string;
  type: string | null;
  serviceCheckStatus: string;
  lastServiceCheckAt: string | null;
  serviceCount: number;
  dataSource: "api" | "adapter";
}

export interface ServiceStatusSnapshot {
  environment_id: string;
  service_id: string;
  host_id: string;
  status: string;
  task_id: string;
  observed_at: string;
  dry_run: boolean;
}

export interface SystemHealth {
  status: string;
  application: string;
}

export interface SystemReady {
  status: string;
  application: string;
  database: string;
  execution_backend: {
    backend: "mock" | "ansible" | string;
    available: boolean;
  };
}

export type TaskStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "PARTIALLY_SUCCEEDED"
  | "FAILED"
  | "TIMED_OUT"
  | "CANCELLED"
  | "REJECTED";

export interface OperationTarget {
  id: string;
  service_id: string;
  host_id: string;
  service_name: string;
  host_name: string;
  status: string;
  output: string | null;
  error_message: string | null;
  duration_ms: number | null;
}

export interface Task {
  id: string;
  environment_id: string;
  environment_name: string;
  action: string;
  scope: string;
  status: TaskStatus;
  requested_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  targets: OperationTarget[];
}

export interface TaskLog {
  id: string;
  task_id: string;
  target_id: string | null;
  stream: string;
  message: string;
  exit_code: number | null;
  dry_run: boolean;
  created_at: string;
}

export interface Audit {
  id: string;
  task_id: string | null;
  event_type: string;
  actor: string;
  message: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  status: "ACTIVE" | "DISABLED";
  roles: string[];
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
}

export interface SecurityContext {
  environment: string;
  executor: string;
  execution_mode: "mock" | "real";
  write_operations: boolean;
  production_operations: boolean;
  approval_required_for_write: boolean;
  safe_mode: boolean;
  real_execution: boolean;
  allowed_actions: string[];
  permissions: string[];
  capabilities: {
    observe: boolean;
    remediate: boolean;
    approve: boolean;
    administer: boolean;
  };
  approval: {
    required_for_write: boolean;
    allow_self_approval: boolean;
    minimum_approvers: number;
    can_request: boolean;
    can_approve: boolean;
    can_reject: boolean;
    can_cancel: boolean;
  };
}

export interface OperationRequest {
  id: string;
  action: "restart";
  status: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
  task_id: string | null;
  reason: string | null;
  created_at: string;
}

export type IncidentStatus =
  "OPEN" | "INVESTIGATING" | "MITIGATING" | "VERIFYING" | "RESOLVED" | "CLOSED" | "FAILED";

export interface IncidentEvidence {
  id: string;
  evidence_type: string;
  source: string;
  source_reference: string;
  summary: string;
  excerpt: string | null;
  observed_at: string;
  collected_at: string;
  collector: string;
  metadata: Record<string, unknown>;
  fingerprint: string;
}

export interface IncidentHypothesis {
  id: string;
  statement: string;
  confidence: number;
  status: string;
  created_at: string;
}

export interface IncidentDiagnosis {
  id: string;
  root_cause: string;
  contributing_factors: string[];
  evidence_ids: string[];
  confidence: number;
  created_at: string;
}

export interface IncidentAction {
  task_id: string;
  action_fingerprint: string;
  created_at: string;
}

export interface Incident {
  id: string;
  title: string;
  summary: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  status: IncidentStatus;
  environment: string;
  service: string;
  source: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  tags: string[];
  version: number;
  evidence: IncidentEvidence[];
  hypotheses: IncidentHypothesis[];
  diagnoses: IncidentDiagnosis[];
  actions: IncidentAction[];
}

export interface IncidentPage {
  items: Incident[];
  offset: number;
  limit: number;
  count: number;
}

export interface TimelineItem {
  id: string;
  kind:
    | "INCIDENT"
    | "EVIDENCE"
    | "HYPOTHESIS"
    | "DIAGNOSIS"
    | "ACTION"
    | "APPROVAL"
    | "VERIFICATION"
    | "WORKFLOW";
  event_type: string;
  occurred_at: string;
  summary: string;
  reference_id: string | null;
  metadata: Record<string, unknown>;
}

export type WorkflowRunStatus =
  "PENDING" | "RUNNING" | "WAITING" | "SUCCEEDED" | "FAILED" | "CANCELLED";

export interface WorkflowRun {
  id: string;
  incident_id: string;
  graph_name: string;
  graph_version: string;
  status: WorkflowRunStatus;
  started_by: string;
  current_node: string | null;
  started_at: string | null;
  finished_at: string | null;
  last_checkpoint_at: string | null;
  last_error: string | null;
  state_references: {
    investigator_mode?: "deterministic" | "llm";
    provider?: string | null;
    model?: string | null;
    prompt_version?: string | null;
    decision_summary?: string;
    uncertainty?: string | null;
    insufficient_evidence?: boolean;
    investigation_evidence_ids?: string[];
  };
  created_at: string;
}
