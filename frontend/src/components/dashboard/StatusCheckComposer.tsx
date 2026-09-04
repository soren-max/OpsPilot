import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SearchCheck, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { catalogApi, tasksApi } from "../../api";
import { ErrorState, LoadingState } from "../PageState";
import {
  CapabilityReason,
  InlineNotice,
  OperationConfirmDialog,
  PageSection,
  StatusBadge,
} from "../OpsUI";
import { queryKeys } from "../../query/queryKeys";
import type { Host, SecurityContext } from "../../types";
import type { OperationCapabilities } from "../../services/operationCapabilities";

type SupportedAction = "status" | "restart";

export function StatusCheckComposer({
  environmentId,
  environmentName,
  environmentLevel,
  security,
  capabilities,
}: {
  environmentId: string;
  environmentName: string;
  environmentLevel: "DEVELOPMENT" | "TEST" | "PRODUCTION";
  security: SecurityContext;
  capabilities: OperationCapabilities;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [serviceId, setServiceId] = useState("");
  const [hostIds, setHostIds] = useState<string[]>([]);
  const [action, setAction] = useState<SupportedAction>("status");
  const [approvalMessage, setApprovalMessage] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const isAnsible = security.executor === "ansible";
  const actionCapability = capabilities[action];
  const services = useQuery({
    queryKey: queryKeys.services(environmentId),
    queryFn: () => catalogApi.services(environmentId),
  });
  const serviceHosts = useQuery({
    queryKey: queryKeys.serviceHosts(serviceId),
    queryFn: () => catalogApi.serviceHosts(serviceId),
    enabled: Boolean(serviceId),
  });
  const visibleServices = useMemo(() => services.data ?? [], [services.data]);
  const visibleHosts = useMemo(() => serviceHosts.data ?? [], [serviceHosts.data]);
  const create = useMutation({
    mutationFn: async () => {
      if (!actionCapability.requiresApproval) {
        return tasksApi.createOperation(environmentId, serviceId, hostIds, action);
      }
      const approval = await tasksApi.createOperationRequest(
        environmentId,
        serviceId,
        hostIds,
        action as "restart",
      );
      if (security.approval.allow_self_approval && security.approval.can_approve) {
        const approved = await tasksApi.approveOperationRequest(approval.id);
        return { task_id: approved.task_id ?? "", status: "PENDING" as const };
      }
      setApprovalMessage(`审批请求 ${approval.id.slice(0, 8)} 已创建，等待审批。`);
      return { task_id: "", status: "PENDING" as const };
    },
    onSuccess: (result) => {
      setConfirmOpen(false);
      void queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
      void queryClient.invalidateQueries({ queryKey: queryKeys.audits });
      if (result.task_id) navigate(`/tasks?task=${result.task_id}`);
    },
  });
  useEffect(() => {
    setServiceId("");
    setHostIds([]);
    setAction("status");
  }, [environmentId]);
  useEffect(() => {
    const requestedAction = searchParams.get("action");
    const requestedService = searchParams.get("service");
    if (
      requestedAction &&
      ["status", "restart"].includes(requestedAction) &&
      capabilities[requestedAction as SupportedAction].canInitiate
    ) {
      setAction(requestedAction as SupportedAction);
    }
    if (requestedService && visibleServices.some((item) => item.id === requestedService)) {
      setServiceId(requestedService);
    }
  }, [capabilities, searchParams, visibleServices]);
  useEffect(() => setHostIds([]), [serviceId]);

  const toggle = (host: Host) =>
    setHostIds((current) =>
      current.includes(host.id) ? current.filter((id) => id !== host.id) : [...current, host.id],
    );
  const submit = () => setConfirmOpen(true);

  return (
    <PageSection
      title={isAnsible ? "受控执行目标" : "状态检查目标"}
      description={
        isAnsible
          ? "逻辑目标由后端校验，连接信息由 operator-owned inventory 管理"
          : "创建任务后自动进入实时任务详情"
      }
    >
      <div className={`operation-console__topline ${isAnsible ? "is-integration" : ""}`}>
        <span>
          {isAnsible ? (
            <ShieldAlert size={17} aria-hidden="true" />
          ) : (
            <SearchCheck size={17} aria-hidden="true" />
          )}{" "}
          {isAnsible ? "ANSIBLE BACKEND" : "STATUS CHECK"}
        </span>
        <strong>{isAnsible ? "受控修复执行" : "后端动态能力判定"}</strong>
      </div>
      <div className="operation-form">
        {services.error && (
          <ErrorState error={services.error} onRetry={() => void services.refetch()} />
        )}
        <label>
          <span>操作</span>
          <select
            value={action}
            onChange={(event) => setAction(event.target.value as SupportedAction)}
            aria-label="选择操作"
          >
            <option value="status" disabled={!capabilities.status.canInitiate}>
              状态检查
            </option>
            <option value="restart" disabled={!capabilities.restart.canInitiate}>
              重启服务（{capabilities.restart.label}）
            </option>
          </select>
        </label>
        <label>
          <span>目标服务</span>
          <select
            value={serviceId}
            onChange={(event) => setServiceId(event.target.value)}
            disabled={services.isLoading}
          >
            <option value="">选择服务</option>
            {visibleServices.map((service) => (
              <option value={service.id} key={service.id}>
                {service.name} · {service.host_count} 主机
              </option>
            ))}
          </select>
        </label>
        <fieldset disabled={!serviceId || serviceHosts.isLoading}>
          <legend>部署主机</legend>
          {serviceHosts.error ? (
            <ErrorState error={serviceHosts.error} onRetry={() => void serviceHosts.refetch()} />
          ) : !serviceId ? (
            <p>先选择服务以获取已部署主机。</p>
          ) : serviceHosts.isLoading ? (
            <LoadingState label="正在读取部署主机" />
          ) : (
            <div className="host-choice-grid">
              {visibleHosts.map((host) => (
                <label key={host.id}>
                  <input
                    type="checkbox"
                    checked={hostIds.includes(host.id)}
                    onChange={() => toggle(host)}
                  />
                  <span>
                    <strong className="mono">{host.name}</strong>
                    <small>{host.description ?? "未提供主机描述"}</small>
                  </span>
                  <StatusBadge status={host.last_status} domain="host" compact />
                </label>
              ))}
            </div>
          )}
        </fieldset>
        <div className="operation-form__footer">
          <span>已选 {hostIds.length} 个目标</span>
          <button
            disabled={
              !actionCapability.canInitiate || !serviceId || !hostIds.length || create.isPending
            }
            onClick={submit}
            className={`button ${action === "restart" ? "button--warning" : "button--primary"}`}
          >
            {create.isPending
              ? "正在创建任务…"
              : actionCapability.requiresApproval
                ? "核对并提交审批"
                : `核对并${action === "status" ? "执行检查" : "重启"}`}
          </button>
        </div>
        <div className="operation-policy-note" role="note">
          <strong>后端有效操作能力</strong>
          <CapabilityReason capability={capabilities.status} />
          <CapabilityReason capability={capabilities.restart} />
          <span>后端安全门不可由手工 API 请求绕过，并记录拒绝审计。</span>
        </div>
        {create.error && (
          <InlineNotice title="操作提交失败" tone="danger">
            {create.error.message}
          </InlineNotice>
        )}
        {approvalMessage && (
          <InlineNotice title="审批请求已创建" tone="info">
            {approvalMessage}
          </InlineNotice>
        )}
      </div>
      <OperationConfirmDialog
        open={confirmOpen}
        action={action}
        environment={`${environmentName} · ${environmentLevel}`}
        service={visibleServices.find((item) => item.id === serviceId)?.name ?? serviceId}
        targetCount={hostIds.length}
        capability={actionCapability}
        pending={create.isPending}
        onConfirm={() => create.mutate()}
        onClose={() => setConfirmOpen(false)}
      />
    </PageSection>
  );
}
