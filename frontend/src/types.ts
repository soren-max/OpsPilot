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
  last_status: string;
  service_count: number;
}

export interface Asset {
  id: string;
  name: string;
  ip: string | null;
  environmentId: string;
  environmentName: string;
  type: string | null;
  connectionStatus: string | null;
  serviceCheckStatus: string;
  lastServiceCheckAt: string | null;
  executorType: string | null;
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
  database: string;
  configuration: string;
  worker: { status: string; poll_seconds: number };
  executor: { type: string; status: string };
  services: {
    required: boolean;
    command_profile: string;
    profile_name: string;
    profile_error: string | null;
    capabilities: Array<"status" | "start" | "stop">;
    preflight: null | {
      status: string;
      checks: Record<string, { status: string; reason: string }>;
    };
  };
  operations_integration?: {
    required: boolean;
    preflight: null | {
      status: string;
      checks: Record<string, { status: string; reason: string }>;
    };
  };
}

export interface CredentialMetadata {
  name: string;
  configured: boolean;
  fingerprint: string | null;
}

export interface IntegrationHost {
  id?: string;
  name: string;
  address: string;
  ssh_port: number;
  ssh_username: string;
  credential_reference: string;
  credential?: CredentialMetadata;
}

export interface IntegrationService {
  id?: string;
  name: string;
  host_names: string[];
}

export interface IntegrationConfigInput {
  environment: { name: string; code: string; level: Environment["environment_level"] };
  hosts: IntegrationHost[];
  services: IntegrationService[];
  execution: {
    services_sh_remote_path: string;
    working_directory: string;
    timeout_seconds: number;
    status_argv: string[];
    start_argv: string[];
    stop_argv: string[];
  };
  parser: {
    type: "regex";
    exit_code_map: Record<string, string>;
    stdout_regex: Record<string, string>;
    stderr_regex: Record<string, string>;
    conflict_policy: "failed" | "first" | "last";
    default_state: string;
    custom_parser: null;
  };
  allowlist: {
    environments: string[];
    hosts: string[];
    services: string[];
    actions: Array<"status" | "start" | "stop">;
  };
}

export interface IntegrationConfig extends IntegrationConfigInput {
  id: string;
  environment_id: string;
  status: "DRAFT" | "VALIDATED" | "READY" | "DISABLED";
  enabled: boolean;
  validation_errors: string[];
  last_ssh_test_ok: boolean;
  last_status_test_ok: boolean;
  last_test_details: Record<string, unknown>;
}

export interface IntegrationTestResult {
  success: boolean;
  result?: "SUCCESS" | "FAILED";
  latency_ms?: number;
  duration_ms?: number;
  exit_code: number;
  parsed_state?: string | null;
  error?: string | null;
  stdout?: string;
  stderr?: string;
  host_fingerprint?: string | null;
  host_key_status?: string;
  credential_fingerprint?: string | null;
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
  environment_mode: "mock" | "integration-test" | "production";
  executor: string;
  execution_mode: "mock" | "real";
  write_operations: boolean;
  production_operations: boolean;
  approval_required_for_write: boolean;
  safe_mode: boolean;
  real_execution: boolean;
  allowed_hosts: string[];
  allowed_services: string[];
  allowed_actions: string[];
  permissions: string[];
  approval: {
    required_for_write: boolean;
    allow_self_approval: boolean;
    minimum_approvers: number;
    can_request: boolean;
    can_approve: boolean;
    can_reject: boolean;
    can_cancel: boolean;
  };
  executor_capabilities: Record<"status" | "start" | "stop", boolean>;
}

export interface OperationRequest {
  id: string;
  action: "start" | "stop";
  status: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
  task_id: string | null;
  reason: string | null;
  created_at: string;
}
