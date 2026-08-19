import { EyeOff, LockKeyhole, Settings2, ShieldCheck } from "lucide-react";
import { ErrorState, LoadingState } from "../components/PageState";
import {
  CapabilityReason,
  InlineNotice,
  PageHeader,
  PolicyBadge,
  PageSection,
  StatusBadge,
} from "../components/OpsUI";
import type { OperationCapabilities } from "../services/operationCapabilities";
import type { SecurityContext, SystemReady } from "../types";

export function SettingsPage({
  security,
  readiness,
  readinessError,
  onRetryReadiness,
  capabilities,
}: {
  security: SecurityContext;
  readiness?: SystemReady;
  readinessError: unknown;
  onRetryReadiness: () => void;
  capabilities: OperationCapabilities;
}) {
  return (
    <div className="page-stack config-page settings-page">
      <PageHeader
        title="系统配置"
        description="只读展示当前执行器、安全策略和白名单；敏感连接信息不会下发到浏览器。"
        actions={
          <span className="page-header__status">
            <LockKeyhole size={15} aria-hidden="true" /> 只读视图
          </span>
        }
      />
      {readinessError ? (
        <ErrorState
          error={
            readinessError instanceof Error ? readinessError : new Error("无法读取系统就绪状态")
          }
          onRetry={onRetryReadiness}
        />
      ) : !readiness ? (
        <LoadingState variant="cards" label="正在读取系统配置" />
      ) : (
        <>
          <div className="settings-summary-strip" aria-label="配置摘要">
            <div>
              <span>Executor 类型</span>
              <strong className="mono">{security.executor}</strong>
            </div>
            <div>
              <span>运行模式</span>
              <strong>{security.environment_mode}</strong>
            </div>
            <div>
              <span>配置可见性</span>
              <strong>脱敏只读</strong>
            </div>
          </div>
          <InlineNotice title="配置为只读" tone="info">
            本页只呈现服务端公开的状态值；路径内容、凭据和远端连接参数不会下发到浏览器。
          </InlineNotice>
          <div className="settings-grid">
            <PageSection
              title="安全策略"
              description="来自系统健康接口与公开安全上下文"
              className="settings-panel"
            >
              <dl className="settings-definition-list">
                <SettingFlag label="write_enabled" enabled={security.write_operations} />
                <SettingFlag label="production_enabled" enabled={security.production_operations} />
                <SettingFlag label="dry_run_only" enabled={security.safe_mode} safe />
                <SettingFlag label="safe_mode" enabled={security.safe_mode} safe />
              </dl>
              <div className="settings-capability-list" aria-label="有效操作能力">
                <CapabilityReason capability={capabilities.status} />
                <CapabilityReason capability={capabilities.start} />
                <CapabilityReason capability={capabilities.stop} />
              </div>
            </PageSection>
            <PageSection
              title="Executor 与 services.sh"
              description="来自 /ready，不执行任何命令"
              className="settings-panel settings-panel--wide"
            >
              <dl className="settings-definition-list settings-definition-list--technical">
                <ReadyValue label="ready" value={readiness.status} ok="ready" />
                <ReadyValue label="executor.type" value={readiness.executor.type} />
                <ReadyValue
                  label="executor.status"
                  value={readiness.executor.status}
                  ok="configured"
                />
                <ReadyValue label="services.required" value={String(readiness.services.required)} />
                <ReadyValue label="services.profile_name" value={readiness.services.profile_name} />
                {readiness.services.preflight && (
                  <ReadyValue
                    label="services.preflight"
                    value={readiness.services.preflight.status}
                    ok="ready"
                  />
                )}
                {Object.entries(readiness.services.preflight?.checks ?? {}).map(
                  ([name, check]) => (
                    <ReadyValue
                      key={name}
                      label={`preflight.${name}`}
                      value={`${check.status}: ${check.reason}`}
                      enabled={check.status === "ok"}
                    />
                  ),
                )}
              </dl>
            </PageSection>
            <PageSection
              title="有效动作与目标保护"
              description="动作是后端合并权限与策略后的有效集合；目标白名单不下发"
              className="settings-panel"
            >
              <Allowlist label="environment" values={[security.environment]} />
              <Allowlist label="host" values={[]} redacted />
              <Allowlist label="service" values={[]} redacted />
              <Allowlist label="action" values={security.allowed_actions} />
            </PageSection>
            <PageSection
              title="敏感配置"
              description="私钥、口令和远端连接参数不向前端暴露"
              className="settings-panel settings-panel--wide"
            >
              <div className="sensitive-config-notice">
                <EyeOff size={18} aria-hidden="true" />
                <div>
                  <strong>已脱敏</strong>
                  <span>SSH 私钥、主机凭据、脚本绝对路径及远端工作目录仅由服务端读取。</span>
                </div>
              </div>
              <dl className="sensitive-field-list">
                {[
                  "ssh.host",
                  "ssh.username",
                  "ssh.private_key",
                  "services.script_path",
                  "remote.working_directory",
                ].map((field) => (
                  <div key={field}>
                    <dt className="mono">{field}</dt>
                    <dd>不下发</dd>
                  </div>
                ))}
              </dl>
            </PageSection>
          </div>
        </>
      )}
    </div>
  );
}

function ReadyValue({
  label,
  value,
  ok,
  enabled: enabledOverride,
}: {
  label: string;
  value: string;
  ok?: string;
  enabled?: boolean;
}) {
  const enabled = enabledOverride ?? (ok ? value === ok : !/not_|pending|unknown/i.test(value));
  return (
    <div>
      <dt className="mono">{label}</dt>
      <dd>
        <PolicyBadge enabled={enabled}>{value}</PolicyBadge>
      </dd>
    </div>
  );
}

function SettingFlag({
  label,
  enabled,
  safe = false,
}: {
  label: string;
  enabled: boolean;
  safe?: boolean;
}) {
  const status = enabled ? (safe ? "HEALTHY" : "RUNNING") : safe ? "UNKNOWN" : "DISABLED";
  return (
    <div>
      <dt className="mono">{label}</dt>
      <dd>
        <StatusBadge status={status} compact />
        <span>{String(enabled)}</span>
      </dd>
    </div>
  );
}

function Allowlist({
  label,
  values,
  redacted = false,
}: {
  label: string;
  values: string[];
  redacted?: boolean;
}) {
  return (
    <div className="allowlist-row">
      <span className="mono">{label}</span>
      <div>
        {redacted ? (
          <span className="redacted-config">
            <EyeOff size={13} aria-hidden="true" /> 服务端校验 · 不下发
          </span>
        ) : values.length ? (
          values.map((value) => (
            <code key={value}>
              <ShieldCheck size={12} aria-hidden="true" />
              {value}
            </code>
          ))
        ) : (
          <span className="muted-value">
            <Settings2 size={13} aria-hidden="true" /> 未配置（默认拒绝）
          </span>
        )}
      </div>
    </div>
  );
}
