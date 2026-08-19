import { KeyRound, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "../auth/authContext";
import {
  CapabilityReason,
  DataTable,
  PageHeader,
  PageSection,
  StatusBadge,
} from "../components/OpsUI";
import type { OperationCapabilities } from "../services/operationCapabilities";

const permissionCatalog = [
  ["service.read", "服务清单与状态"],
  ["host.read", "主机与资产"],
  ["task.read", "任务记录"],
  ["audit.read", "审计记录"],
  ["access.read", "RBAC 配置"],
  ["service.status", "查询服务状态"],
  ["service.start", "启动服务"],
  ["service.stop", "停止服务"],
  ["operation.create", "创建受控操作请求"],
  ["operation.approve", "审批操作请求"],
  ["operation.reject", "驳回操作请求"],
  ["operation.cancel", "取消操作或请求"],
] as const;

export function AccessControlPage({ capabilities }: { capabilities: OperationCapabilities }) {
  const { user } = useAuth();
  const actualPermissions = new Set(user?.permissions ?? []);
  const matrix = [
    {
      action: "status",
      permission: "service.status",
      assigned: actualPermissions.has("service.status"),
      capability: capabilities.status,
      authorizable: true,
    },
    {
      action: "start",
      permission: "service.start",
      assigned: actualPermissions.has("service.start"),
      capability: capabilities.start,
      authorizable: true,
    },
    {
      action: "stop",
      permission: "service.stop",
      assigned: actualPermissions.has("service.stop"),
      capability: capabilities.stop,
      authorizable: true,
    },
    {
      action: "config",
      permission: "config.manage",
      assigned: actualPermissions.has("config.manage"),
      capability: null,
      authorizable: false,
    },
  ];

  return (
    <div className="page-stack config-page access-page">
      <PageHeader
        title="权限管理"
        description="展示当前登录用户、角色、后端实际权限及安全策略合并后的最终有效能力。"
        actions={
          <span className="page-header__status">
            <LockKeyhole size={15} aria-hidden="true" /> 只读矩阵
          </span>
        }
      />
      <div className="access-identity-strip" aria-label="当前用户与角色">
        <div className="access-identity-strip__user">
          <span>
            <UserRound size={18} aria-hidden="true" />
          </span>
          <div>
            <small>当前用户</small>
            <strong>{user?.display_name ?? "未记录"}</strong>
            <code>{user?.username ?? "未记录"}</code>
          </div>
        </div>
        <div>
          <small>账号状态</small>
          <StatusBadge status={user?.status ?? "UNKNOWN"} compact />
        </div>
        <div>
          <small>实际角色</small>
          <strong>{user?.roles.join("、") || "未分配"}</strong>
        </div>
        <div>
          <small>实际权限数</small>
          <strong>{user?.permissions.length ?? 0}</strong>
        </div>
      </div>
      <PageSection
        title="实际权限"
        description="数据直接来自 /auth/me；未返回的权限不会在前端推断。"
      >
        <div className="permission-chip-list" aria-label="当前用户实际权限">
          {(user?.permissions ?? []).map((permission) => (
            <code key={permission}>
              <KeyRound size={12} aria-hidden="true" />
              {permission}
            </code>
          ))}
          {!user?.permissions.length && <span className="unrecorded-value">未分配权限</span>}
        </div>
      </PageSection>
      <PageSection
        title="只读权限矩阵"
        description="RBAC 分配不等于操作可执行；最终能力还必须通过阶段策略和安全门。"
        className="operations-table-card"
      >
        <DataTable ariaLabel="只读权限矩阵">
          <thead>
            <tr>
              <th>Action</th>
              <th>权限要求</th>
              <th>当前分配</th>
              <th>阶段策略</th>
              <th>最终有效</th>
              <th>授权入口</th>
            </tr>
          </thead>
          <tbody>
            {matrix.map((row) => (
              <tr key={row.action}>
                <td>
                  <span className="type-tag">{row.action}</span>
                </td>
                <td className="mono">{row.permission}</td>
                <td>
                  <StatusBadge
                    status={row.assigned ? "SUCCEEDED" : "UNKNOWN"}
                    domain="task"
                    compact
                  />
                </td>
                <td>
                  {row.capability ? (
                    <CapabilityReason capability={row.capability} />
                  ) : (
                    "只读配置，不提供授权入口"
                  )}
                </td>
                <td>
                  <StatusBadge
                    status={row.capability?.canInitiate ? "SUCCEEDED" : "REJECTED"}
                    domain="task"
                    compact
                  />
                </td>
                <td>
                  {row.authorizable ? (
                    <span className="read-only-capability">
                      <ShieldCheck size={13} aria-hidden="true" /> 由后端 RBAC 管理
                    </span>
                  ) : (
                    <button className="matrix-disabled-action" disabled title="当前阶段不可授权">
                      不可授权
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </PageSection>
      <PageSection
        title="资源读取权限"
        description="用于核对当前用户对各只读模块的后端权限标识。"
        className="operations-table-card"
      >
        <DataTable ariaLabel="资源读取权限">
          <thead>
            <tr>
              <th>权限代码</th>
              <th>范围</th>
              <th>实际状态</th>
            </tr>
          </thead>
          <tbody>
            {permissionCatalog.map(([permission, label]) => (
              <tr key={permission}>
                <td className="mono">{permission}</td>
                <td>{label}</td>
                <td>
                  <StatusBadge
                    status={actualPermissions.has(permission) ? "SUCCEEDED" : "UNKNOWN"}
                    domain="task"
                    compact
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </PageSection>
    </div>
  );
}
