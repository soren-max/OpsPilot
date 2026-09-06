import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = (path) => readFile(new URL(path, import.meta.url), "utf8");
const page = await source("../src/pages/ChangesPage.tsx");
const api = await source("../src/api/changes.ts");
const ports = await source("../../backend/app/domain/change/ports.py");

test("approval sends the reviewed fingerprint and rejection stays independent", async () => {
  const calls = [];
  const exports = {};
  const compiled = ts.transpileModule(api, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  vm.runInNewContext(compiled, {
    exports,
    require: () => ({ api: async (path, options) => calls.push({ path, ...options }) }),
  });
  await exports.changesApi.approve("change-1", "Reviewed rollback", "a".repeat(64));
  assert.deepEqual(JSON.parse(calls[0].body), {
    reason: "Reviewed rollback",
    plan_fingerprint: "a".repeat(64),
  });
  await exports.changesApi.reject("change-1", "Insufficient evidence");
  assert.deepEqual(JSON.parse(calls[1].body), { reason: "Insufficient evidence" });
});

test("change detail exposes the complete governed lifecycle", () => {
  for (const step of ["Propose", "Policy", "Approve", "PR", "Review", "Merge", "Sync", "Verify"])
    assert.match(page, new RegExp(step));
  for (const section of [
    "Semantic Diff",
    "Git Revision",
    "GitOps Reconciliation",
    "Change Timeline",
  ])
    assert.match(page, new RegExp(section));
});

test("OpsPilot approval and Git review are visually independent", () => {
  assert.match(page, /OpsPilot Approval/);
  assert.match(page, /Gate A authorizes PR creation only/);
  assert.match(page, /Git Review/);
  assert.match(page, /Gate B independently authorizes merge/);
  assert.match(page, /cannot review, approve, or merge its own pull request/);
  assert.doesNotMatch(ports, /def merge_pull_request/);
});

test("high-risk change decisions require an explicit consequence confirmation", () => {
  assert.match(page, /ChangeDecisionDialog/);
  assert.match(page, /Gate A · HIGH risk/);
  assert.match(page, /does not authorize Git review or merge/);
  assert.match(page, /requires a new governed change/);
});

test("semantic preview leads and raw diff is a technical drawer", () => {
  assert.match(page, /Before/);
  assert.match(page, /After/);
  assert.match(page, /Blast Radius/);
  assert.match(page, /Verification Plan/);
  assert.match(page, /TechnicalDetailDrawer/);
  assert.match(page, /Raw Git diff/);
});

test("unknown Git side effects explain reconciliation and duplicate prevention", () => {
  assert.match(page, /PR creation outcome is indeterminate/);
  assert.match(page, /Automatic duplicate creation is disabled/);
  assert.match(page, /Reconciliation is required/);
});

test("change API exposes bounded decisions but no merge or raw mutation", () => {
  assert.match(api, /\/changes\/\$\{changeId\}\/approve/);
  assert.match(api, /\/changes\/\$\{changeId\}\/reject/);
  assert.match(api, /\/changes\/\$\{changeId\}\/reconcile/);
  assert.doesNotMatch(api, /merge|kubectl|raw.*patch/i);
});
