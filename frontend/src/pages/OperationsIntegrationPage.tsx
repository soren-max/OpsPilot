import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Link2, Play, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { catalogApi, integrationApi } from "../api";
import { InlineNotice, PageHeader, PageSection, StatusBadge } from "../components/OpsUI";
import { ErrorState, LoadingState } from "../components/PageState";
import { queryKeys } from "../query/queryKeys";
import type {
  Environment,
  IntegrationConfig,
  IntegrationConfigInput,
  IntegrationHost,
  IntegrationService,
  IntegrationTestResult,
  SecurityContext,
} from "../types";

const emptyParser: IntegrationConfigInput["parser"] = {
  type: "regex",
  exit_code_map: { "255": "unreachable" },
  stdout_regex: {
    running: "(?i)running|active",
    stopped: "(?i)stopped|inactive",
    failed: "(?i)failed|error",
  },
  stderr_regex: { unreachable: "(?i)unreachable|connection refused|timed out" },
  conflict_policy: "failed",
  default_state: "unknown",
  custom_parser: null,
};

function initialForm(
  environment: Environment,
  hosts: Array<{ id: string; name: string }>,
  services: Array<{ id: string; name: string }>,
): IntegrationConfigInput {
  const hostRows = hosts.map((host) => ({
    id: host.id,
    name: host.name,
    address: "",
    ssh_port: 22,
    ssh_username: "",
    credential_reference: "",
  }));
  return {
    environment: {
      name: environment.name,
      code: environment.code,
      level: environment.environment_level,
    },
    hosts: hostRows,
    services: services.map((service) => ({
      id: service.id,
      name: service.name,
      host_names: hostRows.map((host) => host.name),
    })),
    execution: {
      services_sh_remote_path: "",
      working_directory: "",
      timeout_seconds: 30,
      status_argv: [],
      start_argv: [],
      stop_argv: [],
    },
    parser: emptyParser,
    allowlist: {
      environments: [environment.code],
      hosts: hostRows.map((host) => host.name),
      services: services.map((service) => service.name),
      actions: ["status"],
    },
  };
}

function onboardingForm(): IntegrationConfigInput {
  return {
    environment: { name: "", code: "", level: "TEST" },
    hosts: [{ name: "", address: "", ssh_port: 22, ssh_username: "", credential_reference: "" }],
    services: [{ name: "", host_names: [] }],
    execution: {
      services_sh_remote_path: "",
      working_directory: "",
      timeout_seconds: 30,
      status_argv: [],
      start_argv: [],
      stop_argv: [],
    },
    parser: emptyParser,
    allowlist: { environments: [], hosts: [], services: [], actions: ["status"] },
  };
}

function inputFromConfig(config: IntegrationConfig): IntegrationConfigInput {
  const { environment, hosts, services, execution, parser, allowlist } = config;
  return { environment, hosts, services, execution, parser, allowlist };
}

export function OperationsIntegrationPage({
  environmentId,
  environments,
  security,
}: {
  environmentId: string;
  environments: Environment[];
  security: SecurityContext;
}) {
  const queryClient = useQueryClient();
  const configurations = useQuery({
    queryKey: ["operations-integration", "all"],
    queryFn: integrationApi.list,
  });
  const hosts = useQuery({
    queryKey: queryKeys.hosts(environmentId),
    queryFn: () => catalogApi.hosts(environmentId),
    enabled: Boolean(environmentId),
  });
  const services = useQuery({
    queryKey: queryKeys.services(environmentId),
    queryFn: () => catalogApi.services(environmentId),
    enabled: Boolean(environmentId),
  });
  const credentials = useQuery({
    queryKey: queryKeys.credentials,
    queryFn: integrationApi.credentials,
  });
  const environment = environments.find((item) => item.id === environmentId);
  const config = configurations.data?.find((item) => item.environment_id === environmentId);
  const [form, setForm] = useState<IntegrationConfigInput | null>(null);
  const [result, setResult] = useState<IntegrationTestResult | null>(null);
  const [credentialName, setCredentialName] = useState("");
  const [privateKey, setPrivateKey] = useState("");

  useEffect(() => {
    if (config) setForm(inputFromConfig(config));
    else if (environment && hosts.data && services.data) {
      setForm(initialForm(environment, hosts.data, services.data));
    } else if (!environmentId) {
      setForm(onboardingForm());
    }
    setResult(null);
  }, [config, environment, environmentId, hosts.data, services.data]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["operations-integration"] }),
      queryClient.invalidateQueries({ queryKey: queryKeys.system.ready }),
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.status }),
      queryClient.invalidateQueries({ queryKey: queryKeys.environments }),
      queryClient.invalidateQueries({ queryKey: queryKeys.hosts(environmentId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.services(environmentId) }),
    ]);
  };
  const action = useMutation({
    mutationFn: async ({
      operation,
      hostId,
      serviceId,
    }: {
      operation: "save" | "validate" | "ssh" | "status" | "enable" | "disable";
      hostId?: string;
      serviceId?: string;
    }) => {
      if (!form) throw new Error("配置尚未加载");
      if (operation === "save") {
        const body = normalized(form);
        return environmentId
          ? integrationApi.save(environmentId, body)
          : integrationApi.create(body);
      }
      if (operation === "validate") return integrationApi.validate(environmentId);
      if (operation === "ssh" && hostId) return integrationApi.testSsh(environmentId, hostId);
      if (operation === "status" && hostId && serviceId) {
        return integrationApi.testStatus(environmentId, hostId, serviceId);
      }
      if (operation === "enable") return integrationApi.enable(environmentId);
      if (operation === "disable") return integrationApi.disable(environmentId);
      throw new Error("请先保存包含有效主机和服务关联的配置");
    },
    onSuccess: async (value) => {
      if ("exit_code" in value) setResult(value);
      await refresh();
    },
  });
  const credentialMutation = useMutation({
    mutationFn: () => integrationApi.createCredential(credentialName, privateKey),
    onSuccess: async () => {
      setPrivateKey("");
      await queryClient.invalidateQueries({ queryKey: queryKeys.credentials });
    },
  });
  const canWrite = security.permissions.includes("config.write");
  const canTest = security.permissions.includes("config.test");
  const readyReasons = useMemo(() => config?.validation_errors ?? [], [config?.validation_errors]);
  const sshResults = config?.last_test_details.ssh;
  const sshPassed = (hostId?: string) =>
    Boolean(
      hostId &&
      sshResults &&
      typeof sshResults === "object" &&
      (sshResults as Record<string, { success?: boolean }>)[hostId]?.success,
    );

  if (configurations.isLoading || hosts.isLoading || services.isLoading || credentials.isLoading) {
    return <LoadingState variant="cards" label="正在读取运维接入配置" />;
  }
  const loadError = configurations.error ?? hosts.error ?? services.error ?? credentials.error;
  if (loadError) return <ErrorState error={loadError} onRetry={() => void refresh()} />;
  if (!form) return <ErrorState error={new Error("当前环境不可用")} />;

  const updateHost = (index: number, patch: Partial<IntegrationHost>) =>
    setForm((current) =>
      current
        ? {
            ...current,
            hosts: current.hosts.map((item, i) => (i === index ? { ...item, ...patch } : item)),
          }
        : current,
    );
  const updateService = (index: number, patch: Partial<IntegrationService>) =>
    setForm((current) =>
      current
        ? {
            ...current,
            services: current.services.map((item, i) =>
              i === index ? { ...item, ...patch } : item,
            ),
          }
        : current,
    );
  const busy = action.isPending || credentialMutation.isPending;

  return (
    <div className="page-stack integration-page">
      <PageHeader
        title="运维接入配置"
        description="配置运行期环境、SSH 目标、services.sh、解析规则和白名单。所有保存与测试均经过后端权限、安全校验和审计。"
        actions={<StatusBadge status={config?.enabled ? "READY" : (config?.status ?? "DRAFT")} />}
      />
      <InlineNotice
        title={config?.enabled ? "Ready · 已启用" : "Not Ready · 默认拒绝"}
        tone={config?.enabled ? "success" : "warning"}
      >
        {readyReasons.length
          ? readyReasons.join("；")
          : "保存后需依次完成配置校验、SSH Test、Status Test，再启用。写操作还受平台策略与审批门禁控制。"}
      </InlineNotice>

      <PageSection
        title="Environment"
        description={
          environment
            ? "逻辑环境会复用现有 catalog 数据模型。"
            : "创建第一套真实环境、主机与服务草稿；保存前不会生成现场契约。"
        }
      >
        <div className="integration-form-grid">
          <Field label="名称">
            <input
              value={form.environment.name}
              onChange={(event) =>
                setForm({ ...form, environment: { ...form.environment, name: event.target.value } })
              }
            />
          </Field>
          <Field label="Code">
            <input
              className="mono"
              value={form.environment.code}
              onChange={(event) =>
                setForm({ ...form, environment: { ...form.environment, code: event.target.value } })
              }
            />
          </Field>
          <Field label="Level">
            <select
              value={form.environment.level}
              onChange={(event) =>
                setForm({
                  ...form,
                  environment: {
                    ...form.environment,
                    level: event.target.value as Environment["environment_level"],
                  },
                })
              }
            >
              <option>DEVELOPMENT</option>
              <option>TEST</option>
              <option>PRODUCTION</option>
            </select>
          </Field>
        </div>
      </PageSection>

      <PageSection
        title="Hosts · SSH Connection"
        description="只保存 credential reference；密钥原文不会进入普通配置或 GET 响应。"
      >
        <div className="integration-table-wrap">
          <table className="integration-table">
            <thead>
              <tr>
                <th>Logical Host</th>
                <th>IP / Hostname</th>
                <th>Port</th>
                <th>Username</th>
                <th>Credential</th>
                <th>Test / Remove</th>
              </tr>
            </thead>
            <tbody>
              {form.hosts.map((host, index) => {
                const savedHost = config?.hosts.find((item) => item.name === host.name);
                return (
                  <tr key={`${host.id ?? "new"}-${index}`}>
                    <td>
                      <input
                        value={host.name}
                        onChange={(event) => updateHost(index, { name: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        value={host.address}
                        onChange={(event) => updateHost(index, { address: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        max={65535}
                        value={host.ssh_port}
                        onChange={(event) =>
                          updateHost(index, { ssh_port: Number(event.target.value) })
                        }
                      />
                    </td>
                    <td>
                      <input
                        value={host.ssh_username}
                        onChange={(event) =>
                          updateHost(index, { ssh_username: event.target.value })
                        }
                      />
                    </td>
                    <td>
                      <select
                        value={host.credential_reference}
                        onChange={(event) =>
                          updateHost(index, { credential_reference: event.target.value })
                        }
                      >
                        <option value="">选择凭据</option>
                        {credentials.data?.map((item) => (
                          <option key={item.name} value={item.name}>
                            {item.name} · {item.configured ? "configured" : "not configured"}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <div className="integration-row-actions">
                        <button
                          className="secondary-button"
                          disabled={
                            !canTest ||
                            busy ||
                            !savedHost?.id ||
                            !["VALIDATED", "READY"].includes(config?.status ?? "") ||
                            config?.enabled
                          }
                          onClick={() => action.mutate({ operation: "ssh", hostId: savedHost?.id })}
                        >
                          <Link2 size={14} /> Test SSH
                        </button>
                        <button
                          className="icon-button"
                          aria-label={`移除主机 ${host.name}`}
                          disabled={busy || form.hosts.length === 1}
                          onClick={() =>
                            setForm({
                              ...form,
                              hosts: form.hosts.filter((_, itemIndex) => itemIndex !== index),
                            })
                          }
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <button
          className="secondary-button"
          disabled={!canWrite || busy}
          onClick={() =>
            setForm({
              ...form,
              hosts: [
                ...form.hosts,
                {
                  name: "",
                  address: "",
                  ssh_port: 22,
                  ssh_username: "opspilot",
                  credential_reference: "",
                },
              ],
            })
          }
        >
          <Plus size={15} /> Add Host
        </button>
        <div className="allowlist-preview">
          {credentials.data?.map((item) => (
            <code key={item.name}>
              {item.name}: {item.configured ? "configured" : "not configured"} ·{" "}
              {item.fingerprint ?? "no fingerprint"}
            </code>
          ))}
        </div>
        <details className="credential-create">
          <summary>
            <KeyRound size={15} /> 创建宿主机凭据
          </summary>
          <div className="integration-form-grid">
            <Field label="Credential name">
              <input
                value={credentialName}
                onChange={(event) => setCredentialName(event.target.value)}
              />
            </Field>
            <Field label="Private key（仅提交，不回显）">
              <textarea
                value={privateKey}
                onChange={(event) => setPrivateKey(event.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
            </Field>
            <button
              className="secondary-button"
              disabled={!canWrite || busy || !credentialName || !privateKey}
              onClick={() => credentialMutation.mutate()}
            >
              <KeyRound size={15} /> 安全保存凭据
            </button>
          </div>
        </details>
      </PageSection>

      <PageSection title="Services" description="服务与环境、主机关联；主机名用逗号分隔。">
        <div className="integration-table-wrap">
          <table className="integration-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Associated Hosts</th>
                <th>Status Tests / Remove</th>
              </tr>
            </thead>
            <tbody>
              {form.services.map((service, index) => {
                const savedService = config?.services.find((item) => item.name === service.name);
                return (
                  <tr key={`${service.id ?? "new"}-${index}`}>
                    <td>
                      <input
                        value={service.name}
                        onChange={(event) => updateService(index, { name: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        value={service.host_names.join(",")}
                        onChange={(event) =>
                          updateService(index, { host_names: splitCsv(event.target.value) })
                        }
                      />
                    </td>
                    <td>
                      <div className="integration-row-actions">
                        {service.host_names.map((hostName) => {
                          const savedHost = config?.hosts.find((item) => item.name === hostName);
                          return (
                            <button
                              key={hostName}
                              className="secondary-button"
                              disabled={
                                !canTest ||
                                busy ||
                                !savedHost?.id ||
                                !savedService?.id ||
                                !sshPassed(savedHost?.id) ||
                                config?.enabled
                              }
                              onClick={() =>
                                action.mutate({
                                  operation: "status",
                                  hostId: savedHost?.id,
                                  serviceId: savedService?.id,
                                })
                              }
                            >
                              <Play size={14} /> Test Status · {hostName}
                            </button>
                          );
                        })}
                        <button
                          className="icon-button"
                          aria-label={`移除服务 ${service.name}`}
                          disabled={busy || form.services.length === 1}
                          onClick={() =>
                            setForm({
                              ...form,
                              services: form.services.filter((_, itemIndex) => itemIndex !== index),
                            })
                          }
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <button
          className="secondary-button"
          disabled={!canWrite || busy}
          onClick={() =>
            setForm({
              ...form,
              services: [
                ...form.services,
                { name: "", host_names: form.hosts[0]?.name ? [form.hosts[0].name] : [] },
              ],
            })
          }
        >
          <Plus size={15} /> Add Service
        </button>
      </PageSection>

      <PageSection
        title="Execution Profile"
        description="这里只配置 services.sh 的 status/start/stop argv 契约；禁止填写 ansible-playbook、yml 或任意命令。单服务 start/stop 必须显式包含 {service}。"
      >
        <div className="integration-form-grid">
          <Field label="services.sh remote path">
            <input
              className="mono"
              value={form.execution.services_sh_remote_path}
              onChange={(event) =>
                setForm({
                  ...form,
                  execution: { ...form.execution, services_sh_remote_path: event.target.value },
                })
              }
            />
          </Field>
          <Field label="working_directory">
            <input
              className="mono"
              value={form.execution.working_directory}
              onChange={(event) =>
                setForm({
                  ...form,
                  execution: { ...form.execution, working_directory: event.target.value },
                })
              }
            />
          </Field>
          <Field label="Timeout (seconds)">
            <input
              type="number"
              min={1}
              max={300}
              value={form.execution.timeout_seconds}
              onChange={(event) =>
                setForm({
                  ...form,
                  execution: { ...form.execution, timeout_seconds: Number(event.target.value) },
                })
              }
            />
          </Field>
          <Field label="status argv">
            <input
              className="mono"
              value={form.execution.status_argv.join(" ")}
              onChange={(event) =>
                setForm({
                  ...form,
                  execution: {
                    ...form.execution,
                    status_argv: event.target.value.trim().split(/\s+/),
                  },
                })
              }
            />
          </Field>
          {(["start", "stop"] as const).map((operation) => (
            <Field key={operation} label={`${operation} argv`}>
              <input
                className="mono"
                value={form.execution[`${operation}_argv`].join(" ")}
                disabled={!form.allowlist.actions.includes(operation)}
                onChange={(event) =>
                  setForm({
                    ...form,
                    execution: {
                      ...form.execution,
                      [`${operation}_argv`]: event.target.value.trim()
                        ? event.target.value.trim().split(/\s+/)
                        : [],
                    },
                  })
                }
              />
            </Field>
          ))}
        </div>
      </PageSection>

      <PageSection
        title="Output Parser"
        description="规则冲突默认失败；SSH 255 映射为 unreachable。"
      >
        <div className="integration-form-grid">
          {(["running", "stopped", "failed"] as const).map((state) => (
            <Field key={state} label={`${state} stdout regex`}>
              <input
                className="mono"
                value={form.parser.stdout_regex[state] ?? ""}
                onChange={(event) =>
                  setForm({
                    ...form,
                    parser: {
                      ...form.parser,
                      stdout_regex: { ...form.parser.stdout_regex, [state]: event.target.value },
                    },
                  })
                }
              />
            </Field>
          ))}
          <Field label="unreachable stderr regex">
            <input
              className="mono"
              value={form.parser.stderr_regex.unreachable ?? ""}
              onChange={(event) =>
                setForm({
                  ...form,
                  parser: {
                    ...form.parser,
                    stderr_regex: { ...form.parser.stderr_regex, unreachable: event.target.value },
                  },
                })
              }
            />
          </Field>
          <Field label="Exit 255">
            <input value="unreachable" disabled />
          </Field>
        </div>
      </PageSection>

      <PageSection
        title="Allowlist · Ready Status"
        description="保存时按当前对象生成精确白名单；平台安全开关始终优先。"
      >
        {!security.write_operations && (
          <InlineNotice title="平台策略禁止" tone="warning">
            write_enabled=false，管理员不能启用 start/stop；请由平台部署策略显式开放。
          </InlineNotice>
        )}
        {form.environment.level === "PRODUCTION" && !security.production_operations && (
          <InlineNotice title="平台策略禁止" tone="warning">
            production_operations_enabled=false，生产环境不能启用 start/stop。
          </InlineNotice>
        )}
        <div className="integration-row-actions">
          {(["status", "start", "stop"] as const).map((operation) => {
            const writeBlocked = operation !== "status" && !security.write_operations;
            const productionBlocked =
              operation !== "status" &&
              form.environment.level === "PRODUCTION" &&
              !security.production_operations;
            return (
              <label key={operation} className="integration-field">
                <span>{operation}</span>
                <input
                  type="checkbox"
                  checked={form.allowlist.actions.includes(operation)}
                  disabled={operation === "status" || writeBlocked || productionBlocked}
                  title={writeBlocked || productionBlocked ? "平台策略禁止" : undefined}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      allowlist: {
                        ...form.allowlist,
                        actions: event.target.checked
                          ? [...form.allowlist.actions, operation]
                          : form.allowlist.actions.filter((item) => item !== operation),
                      },
                    })
                  }
                />
              </label>
            );
          })}
        </div>
        <div className="allowlist-preview">
          <code>environment: {form.environment.code}</code>
          <code>hosts: {form.hosts.map((item) => item.name).join(", ") || "empty"}</code>
          <code>services: {form.services.map((item) => item.name).join(", ") || "empty"}</code>
          <code>actions: {form.allowlist.actions.join(", ")}</code>
        </div>
        <div className="integration-actions">
          <button
            className="primary-button"
            disabled={!canWrite || busy}
            onClick={() => action.mutate({ operation: "save" })}
          >
            <Save size={15} /> Save
          </button>
          <button
            className="secondary-button"
            disabled={!canWrite || busy || !config || config.enabled}
            onClick={() => action.mutate({ operation: "validate" })}
          >
            <ShieldCheck size={15} /> Validate
          </button>
          <button
            className="primary-button"
            disabled={!canWrite || busy || config?.status !== "READY" || config.enabled}
            onClick={() => action.mutate({ operation: "enable" })}
          >
            Enable
          </button>
          <button
            className="danger-button"
            disabled={!canWrite || busy || !config?.enabled}
            onClick={() => action.mutate({ operation: "disable" })}
          >
            Disable
          </button>
        </div>
        {action.error && (
          <InlineNotice title="操作失败" tone="danger">
            {action.error.message}
          </InlineNotice>
        )}
        {credentialMutation.error && (
          <InlineNotice title="凭据保存失败" tone="danger">
            {credentialMutation.error.message}
          </InlineNotice>
        )}
        {result && (
          <div className="test-result">
            <strong>{result.success ? "SUCCESS" : "FAILED"}</strong>
            <dl>
              <div>
                <dt>Duration</dt>
                <dd>{result.duration_ms ?? result.latency_ms ?? 0} ms</dd>
              </div>
              <div>
                <dt>Exit code</dt>
                <dd>{result.exit_code}</dd>
              </div>
              <div>
                <dt>Parsed state</dt>
                <dd>{result.parsed_state ?? "-"}</dd>
              </div>
              <div>
                <dt>Host key</dt>
                <dd>{result.host_key_status ?? "-"}</dd>
              </div>
            </dl>
            {result.stdout && <pre>{result.stdout}</pre>}
            {(result.stderr || result.error) && <pre>{result.stderr || result.error}</pre>}
          </div>
        )}
      </PageSection>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="integration-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalized(form: IntegrationConfigInput): IntegrationConfigInput {
  return {
    ...form,
    hosts: form.hosts.map((host) => ({
      id: host.id,
      name: host.name,
      address: host.address,
      ssh_port: host.ssh_port,
      ssh_username: host.ssh_username,
      credential_reference: host.credential_reference,
    })),
    allowlist: {
      environments: [form.environment.code],
      hosts: form.hosts.map((item) => item.name),
      services: form.services.map((item) => item.name),
      actions: form.allowlist.actions,
    },
  };
}
