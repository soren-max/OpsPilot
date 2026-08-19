import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const composer = await readFile(
  new URL("../src/components/dashboard/StatusCheckComposer.tsx", import.meta.url),
  "utf8",
);
const services = await readFile(new URL("../src/pages/ServicesPage.tsx", import.meta.url), "utf8");
const client = await readFile(new URL("../src/api/client.ts", import.meta.url), "utf8");
const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
const policy = await readFile(
  new URL("../src/services/operationCapabilities.ts", import.meta.url),
  "utf8",
);

test("start and stop are controlled by effective permissions and policy", () => {
  assert.match(composer, /<option value="status" disabled=\{!capabilities\.status\.canInitiate\}>/);
  assert.match(composer, /disabled=\{!capabilities\.start\.canInitiate\}/);
  assert.match(composer, /disabled=\{!capabilities\.stop\.canInitiate\}/);
  assert.match(policy, /EXECUTABLE/);
  assert.match(policy, /ENVIRONMENT_POLICY_DENIED/);
  assert.match(policy, /PERMISSION_DENIED/);
  assert.match(policy, /EXECUTOR_UNSUPPORTED/);
  assert.match(policy, /PROFILE_NOT_CONFIGURED/);
  assert.match(policy, /PRODUCTION_OPERATION_DENIED/);
  assert.match(policy, /APPROVAL_REQUIRED/);
  assert.match(policy, /operation\.create/);
  assert.match(composer, /tasksApi\.createOperationRequest/);
  assert.match(composer, /security\.approval\.allow_self_approval/);
  assert.match(composer, /tasksApi\.approveOperationRequest/);
  assert.match(policy, /当前环境未启用写操作。/);
  assert.match(services, /CapabilityReason capability=\{startCapability\}/);
});

test("one resolver owns every user-facing operation outcome", () => {
  assert.match(app, /resolveOperationCapabilities\(/);
  assert.equal((app.match(/resolveOperationCapabilities\(/g) ?? []).length, 1);
  for (const label of [
    "立即可执行",
    "需要审批",
    "无权限",
    "环境策略禁止",
    "Executor 不支持",
    "Profile 未配置",
    "生产操作禁止",
  ]) {
    assert.match(policy, new RegExp(label));
  }
  assert.doesNotMatch(services, /executor_capabilities|allowed_actions\.includes|write_operations/);
});

test("production API uses a relative default base URL", () => {
  assert.match(client, /VITE_API_BASE_URL \?\? "\/api\/v1"/);
  assert.doesNotMatch(client, /localhost:8000\/api\/v1/);
});
