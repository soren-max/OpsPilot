import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(
  new URL("../src/pages/OperationsIntegrationPage.tsx", import.meta.url),
  "utf8",
);
const api = await readFile(new URL("../src/api/integration.ts", import.meta.url), "utf8");

test("operations integration UI exposes the fail-closed configuration workflow", () => {
  for (const label of ["Save", "Validate", "Test SSH", "Test Status", "Enable", "Disable"]) {
    assert.match(page, new RegExp(label));
  }
  assert.match(page, /\["status", "start", "stop"\]/);
  assert.match(page, /平台策略禁止/);
  assert.match(page, /!security\.write_operations/);
  assert.match(page, /start_argv/);
  assert.match(page, /stop_argv/);
  assert.match(page, /credential reference/);
  assert.match(page, /Private key（仅提交，不回显）/);
});

test("configuration writes and tests are backend API calls", () => {
  assert.match(api, /method: "PUT"/);
  assert.match(api, /\/validate/);
  assert.match(api, /\/test-ssh\//);
  assert.match(api, /\/test-status\//);
  assert.doesNotMatch(page, /application\.site\.yml|hosts\.conf/);
});
