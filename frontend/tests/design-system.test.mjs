import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("design tokens match the OPSPILOT operations console contract", async () => {
  const tokens = await source("../src/design-tokens.css");

  for (const token of [
    "--opspilot-bg",
    "--opspilot-surface",
    "--opspilot-surface-subtle",
    "--opspilot-border",
    "--opspilot-border-strong",
    "--opspilot-text",
    "--opspilot-text-secondary",
    "--opspilot-text-disabled",
    "--opspilot-primary",
    "--opspilot-primary-hover",
    "--opspilot-success",
    "--opspilot-warning",
    "--opspilot-danger",
    "--opspilot-info",
  ]) {
    assert.match(tokens, new RegExp(`${token}:`));
  }
  assert.match(tokens, /--opspilot-bg:\s*#f4f4f4/i);
  assert.match(tokens, /--opspilot-primary:\s*#0f62fe/i);
  assert.match(tokens, /--opspilot-radius-sm:\s*4px/i);
  assert.match(tokens, /--opspilot-radius-md:\s*6px/i);
  assert.match(tokens, /--glass-blur:\s*none/i);
  assert.match(tokens, /--shadow-panel:\s*none/i);
  assert.ok(contrastRatio("#525252", "#ffffff") >= 4.5);
  assert.ok(contrastRatio("#c6c6c6", "#262626") >= 4.5);
});

test("dashboard uses the operations operations information architecture", async () => {
  const dashboard = await source("../src/pages/DashboardPage.tsx");

  for (const label of [
    "系统状态",
    "总资产",
    "服务检查正常主机",
    "异常资产",
    "Running",
    "Stopped",
    "Unknown",
    "最近任务",
    "风险提醒",
  ]) {
    assert.match(dashboard, new RegExp(label));
  }
  assert.match(dashboard, /systemApi\.health/);
  assert.match(dashboard, /tasksApi\.statusSnapshots/);
  assert.match(dashboard, /dashboard-workbench/);
  assert.match(dashboard, /quick-status-check/);
});

test("responsive and reduced-motion safeguards remain present", async () => {
  const styles = await source("../src/reference-console.css");
  const operationsStyles = await source("../src/operations-console.css");

  assert.match(styles, /@media \(max-width: 1180px\)/);
  assert.match(styles, /@media \(max-width: 700px\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(operationsStyles, /@media \(max-width: 1366px\)/);
  assert.match(operationsStyles, /@media \(max-width: 860px\)/);
  assert.match(operationsStyles, /@media \(prefers-reduced-motion: reduce\)/);
});

test("shell owns one viewport-bound, keyboard-scrollable main content region", async () => {
  const shell = await source("../src/components/AppShell.tsx");
  const referenceStyles = await source("../src/reference-console.css");
  const operationsStyles = await source("../src/operations-console.css");

  assert.match(shell, /id="main-content" className="ops-content" tabIndex=\{0\}/);
  assert.doesNotMatch(referenceStyles, /html,\s*body,\s*#root\s*\{[^}]*overflow:\s*hidden/s);
  assert.match(referenceStyles, /\.ops-main\s*\{[^}]*min-height:\s*0/s);
  assert.match(
    referenceStyles,
    /\.ops-content\s*\{[^}]*min-height:\s*0[^}]*overflow-y:\s*auto/s,
  );
  assert.match(
    operationsStyles,
    /\.ops-shell\s*\{[^}]*height:\s*100dvh[^}]*overflow:\s*hidden/s,
  );
  assert.doesNotMatch(shell, /onWheel|addEventListener\([^)]*["']wheel/);
});

test("integration execution remains explicit while write controls are policy driven", async () => {
  const composer = await source("../src/components/dashboard/StatusCheckComposer.tsx");
  const policy = await source("../src/services/operationCapabilities.ts");
  const capabilityUi = await source("../src/components/ops/Capability.tsx");
  const shell = await source("../src/components/AppShell.tsx");
  const styles = await source("../src/reference-console.css");

  assert.match(shell, /Linux 控制节点 · 本地 services\.sh/);
  assert.match(composer, /capabilities\.start\.canInitiate/);
  assert.match(composer, /capabilities\.stop\.canInitiate/);
  assert.match(policy, /ENVIRONMENT_POLICY_DENIED/);
  assert.match(policy, /APPROVAL_REQUIRED/);
  assert.match(capabilityUi, /role="dialog"/);
  assert.match(styles, /\.global-bar__execution\.is-integration/);
  assert.match(styles, /var\(--opspilot-warning\)/);
});

test("settings and routing metadata are present", async () => {
  const app = await source("../src/App.tsx");
  const routes = await source("../src/routing/routeMeta.ts");
  const settings = await source("../src/pages/SettingsPage.tsx");

  assert.match(app, /path="\/settings"/);
  assert.match(routes, /系统配置/);
  assert.match(settings, /敏感配置/);
  assert.match(settings, /只读视图/);
  assert.match(app, /systemApi\.ready/);
  assert.match(settings, /services\.preflight/);
  assert.match(settings, /preflight\.\$\{name\}/);
  assert.match(settings, /check\.reason/);
});

test("dashboard exposes readiness and policy facts without synthetic trends", async () => {
  const dashboard = await source("../src/pages/DashboardPage.tsx");

  for (const label of [
    "API",
    "Worker",
    "Readiness",
    "Environment level",
    "Executor",
    "Command profile",
    "Write policy",
    "Production policy",
  ]) {
    assert.match(dashboard, new RegExp(label));
  }
  assert.match(dashboard, /readiness\.services\.profile_name/);
  assert.doesNotMatch(dashboard, /sparkline|trend|Math\.random/);
});

test("service and asset pages preserve controlled operations operations", async () => {
  const services = await source("../src/pages/ServicesPage.tsx");
  const hosts = await source("../src/pages/HostsPage.tsx");
  const assets = await source("../src/services/assetService.ts");

  assert.match(services, /capabilities\.start/);
  assert.match(services, /capabilities\.stop/);
  assert.match(services, /后端有效操作能力/);
  assert.match(services, /catalogApi\.hostServices/);
  assert.match(services, /按主机筛选服务/);
  assert.match(services, /环境：\{environmentName\}/);
  assert.match(services, /to=\{`\/\?action=start/);
  assert.match(services, /to=\{`\/\?action=stop/);
  assert.match(hosts, /assetService\.list/);
  assert.match(hosts, /搜索资产名称或 IP/);
  assert.match(hosts, /按环境筛选/);
  assert.match(hosts, /connectionStatus/);
  assert.match(hosts, /serviceCheckStatus/);
  assert.match(hosts, /lastServiceCheckAt/);
  assert.match(hosts, /未提供/);
  assert.doesNotMatch(hosts, /lastConnectedAt/);
  assert.match(assets, /ip: null/);
  assert.match(assets, /type: null/);
});

test("task and audit details expose structured evidence without inventing fields", async () => {
  const tasks = await source("../src/pages/TasksPage.tsx");
  const execution = await source("../src/components/ops/Execution.tsx");
  const audits = await source("../src/pages/AuditsPage.tsx");

  for (const label of ["环境", "资产", "服务", "发起人", "开始时间"]) {
    assert.match(tasks, new RegExp(label));
  }
  for (const step of ["用户请求", "权限校验", "Executor", "脚本执行", "结果解析"]) {
    assert.match(execution, new RegExp(step));
  }
  assert.match(execution, /执行器类型未记录/);
  assert.match(execution, /stdout \+ stderr/);
  assert.match(execution, /按执行目标筛选日志/);
  assert.match(audits, /企业操作审计列表/);
  assert.match(audits, /来源 IP/);
  assert.match(audits, /Executor/);
  assert.match(audits, /未记录/);
  assert.match(audits, /DetailDrawer/);
});

test("RBAC and configuration remain factual and read-only", async () => {
  const access = await source("../src/pages/AccessControlPage.tsx");
  const settings = await source("../src/pages/SettingsPage.tsx");
  const composer = await source("../src/components/dashboard/StatusCheckComposer.tsx");

  for (const label of ["当前用户", "实际角色", "实际权限", "只读权限矩阵"]) {
    assert.match(access, new RegExp(label));
  }
  for (const action of ["status", "start", "stop", "config"]) {
    assert.match(access, new RegExp(`action: "${action}"`));
  }
  assert.match(access, /capabilities\.start/);
  assert.match(access, /capabilities\.stop/);
  assert.match(access, /operation\.create/);
  assert.match(access, /service\.status/);
  assert.match(access, /不可授权/);
  assert.match(settings, /服务端校验 · 不下发/);
  assert.match(settings, /ssh\.private_key/);
  assert.match(settings, /services\.script_path/);
  assert.doesNotMatch(composer, /security\.allowed_hosts\.includes/);
  assert.doesNotMatch(composer, /security\.allowed_services\.includes/);
});

test("acceptance states and viewport contracts are explicit", async () => {
  const app = await source("../src/App.tsx");
  const pageState = await source("../src/components/PageState.tsx");
  const shell = await source("../src/components/AppShell.tsx");
  const styles = await source("../src/operations-console.css");

  assert.match(app, /lazy\(\(\) => import/);
  assert.match(app, /Suspense fallback/);
  assert.match(pageState, /权限不足/);
  assert.match(pageState, /网络或服务连接异常/);
  assert.match(pageState, /NetworkStatusBanner/);
  assert.match(shell, /NetworkStatusBanner/);
  assert.match(styles, /@media \(min-width: 1280px\) and \(max-width: 1599px\)/);
  assert.match(styles, /grid-template-columns: 212px minmax\(0, 1fr\)/);
  assert.match(styles, /@media \(min-width: 861px\) and \(max-width: 1279px\)/);
  assert.match(styles, /grid-template-columns: 82px minmax\(0, 1fr\)/);
  assert.match(styles, /\.access-page \.operations-table-card \.data-table th:last-child/);
  assert.match(styles, /@media \(min-width: 1920px\)/);
  assert.match(styles, /@media \(min-width: 2400px\)/);
  assert.match(styles, /width: min\(100%, 2048px\)/);
  assert.match(styles, /overscroll-behavior-inline: contain/);
});

test("large-screen layout uses shared page tiers and viewport bands", async () => {
  const tokens = await source("../src/design-tokens.css");
  const styles = await source("../src/operations-console.css");

  assert.match(tokens, /--opspilot-page-config-max:\s*1360px/);
  assert.match(tokens, /--opspilot-page-dashboard-max:\s*1760px/);
  assert.match(tokens, /--opspilot-page-data-max:\s*1960px/);
  assert.match(styles, /@media \(max-width: 1279px\)/);
  assert.match(styles, /@media \(min-width: 1280px\) and \(max-width: 1599px\)/);
  assert.match(styles, /@media \(min-width: 1600px\) and \(max-width: 2199px\)/);
  assert.match(styles, /@media \(min-width: 2200px\)/);
  assert.match(styles, /\.ops-content > \.dashboard-page/);
  assert.match(styles, /\.ops-content > \.data-page/);
});

test("task detail expands for logs and keeps nowrap scrolling local", async () => {
  const tasks = await source("../src/pages/TasksPage.tsx");
  const execution = await source("../src/components/ops/Execution.tsx");
  const styles = await source("../src/operations-console.css");

  assert.match(tasks, /detail-drawer--task/);
  assert.match(tasks, /错误码与解析/);
  assert.match(tasks, /stderr \/ stdout/);
  assert.match(tasks, /退出码/);
  assert.match(execution, /is-nowrap/);
  assert.match(execution, /不折行/);
  assert.match(styles, /--opspilot-task-drawer-max/);
  assert.match(styles, /@container \(min-width: 840px\)/);
  assert.match(styles, /white-space:\s*pre;/);
});

test("the acceptance layer uses semantic tokens and keeps one import boundary", async () => {
  const main = await source("../src/main.tsx");
  const styles = await source("../src/operations-console.css");

  assert.equal((main.match(/operations-console\.css/g) ?? []).length, 1);
  assert.doesNotMatch(styles, /#[0-9a-f]{3,8}\b/i);
  assert.doesNotMatch(styles, /\brgba?\(/i);
  assert.doesNotMatch(styles, /var\(--ds-/);
  assert.match(styles, /var\(--opspilot-text\)/);
  assert.match(styles, /prefers-reduced-motion/);
});

test("P1 uses PageSection with a temporary SectionCard compatibility alias", async () => {
  const layout = await source("../src/components/ops/Layout.tsx");
  const pages = await Promise.all(
    [
      "DashboardPage",
      "ServicesPage",
      "HostsPage",
      "TasksPage",
      "AuditsPage",
      "AccessControlPage",
      "SettingsPage",
    ].map((name) => source(`../src/pages/${name}.tsx`)),
  );

  assert.match(layout, /export function PageSection/);
  assert.match(layout, /export const SectionCard = PageSection/);
  for (const page of pages) {
    assert.match(page, /PageSection/);
    assert.doesNotMatch(page, /<SectionCard/);
  }
});

test("task and audit drawers keep failure evidence ahead of output and timeline", async () => {
  const tasks = await source("../src/pages/TasksPage.tsx");
  const audits = await source("../src/pages/AuditsPage.tsx");

  for (const page of [tasks, audits]) {
    const status = Math.max(page.indexOf("总体状态"), page.indexOf("执行结果"));
    const error = page.indexOf("错误码与解析");
    const output = page.indexOf("stderr / stdout");
    const timeline = Math.max(
      page.indexOf("结构化执行链"),
      page.indexOf("时间线"),
      page.indexOf("Timeline"),
    );
    assert.ok(status >= 0 && status < error);
    assert.ok(error < output);
    assert.ok(output < timeline);
  }
});

test("legacy CSS consumers use semantic OPSPILOT tokens without decorative effects", async () => {
  const css = (
    await Promise.all(
      ["styles.css", "reference-console.css", "operations-console.css"].map((name) =>
        source(`../src/${name}`),
      ),
    )
  ).join("\n");

  assert.doesNotMatch(css, /var\(--ds-/);
  assert.doesNotMatch(css, /#[0-9a-f]{3,8}\b/i);
  assert.doesNotMatch(css, /\brgba?\(/i);
  assert.doesNotMatch(css, /(?:linear|radial)-gradient\(/i);
  assert.doesNotMatch(css, /backdrop-filter:\s*blur\(/i);
});

function contrastRatio(foreground, background) {
  const values = [foreground, background].map(relativeLuminance);
  return (Math.max(...values) + 0.05) / (Math.min(...values) + 0.05);
}

function relativeLuminance(hex) {
  const channels = hex
    .slice(1)
    .match(/../g)
    .map((value) => Number.parseInt(value, 16) / 255)
    .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}
