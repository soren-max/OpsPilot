import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path) => readFile(new URL(path, import.meta.url), "utf8");

const page = await source("../src/pages/IncidentsPage.tsx");
const operations = await source("../src/components/incidents/IncidentOperations.tsx");
const drawer = await source("../src/components/ops/Drawer.tsx");
const status = await source("../src/components/ops/Status.tsx");
const shell = await source("../src/components/AppShell.tsx");
const styles = await source("../src/operations-console.css");
const api = await source("../src/api/incidents.ts");
const app = await source("../src/App.tsx");

test("incident UI exposes the durable lifecycle without a chat surface", () => {
  for (const section of [
    "Overview",
    "Evidence",
    "Hypotheses",
    "Diagnosis",
    "Action Proposal",
    "Approval",
    "Execution",
    "Verification",
    "Timeline",
  ]) {
    assert.match(page, new RegExp(section));
  }
  for (const step of [
    "Observe",
    "Investigate",
    "Diagnose",
    "Policy",
    "Approval",
    "Execute",
    "Verify",
  ]) {
    assert.match(operations, new RegExp(`label: "${step}"`));
  }
  for (const state of ["COMPLETE", "ACTIVE", "WAITING", "FAILED", "SKIPPED"]) {
    assert.match(operations, new RegExp(state));
  }
  assert.doesNotMatch(page, /Chat|conversation|message composer/i);
  assert.match(app, /incidents\/:incidentId\?/);
});

test("incident queue supports operational search and filters", () => {
  for (const label of [
    "Severity",
    "Status",
    "Service",
    "Environment",
    "Title",
    "Evidence",
    "Action",
    "Updated",
  ]) {
    assert.match(page, new RegExp(label));
  }
  assert.match(page, /SearchInput/);
  assert.match(page, /Clear filters/);
  assert.match(page, /LoadingState variant="table"/);
  assert.match(page, /No matching incidents/);
  assert.match(page, /onKeyDown/);
});

test("incident evidence shows typed sources, provenance, and an untrusted-log boundary", () => {
  for (const mapping of [
    'METRIC: { label: "Metric"',
    'LOG: { label: "Log"',
    'TICKET: { label: "Ticket"',
    'SERVICE_STATUS: { label: "Service status"',
  ]) {
    assert.match(operations, new RegExp(mapping.replace(/[{}]/g, "\\$&")));
  }
  assert.match(operations, /evidence\.source/);
  assert.match(operations, /evidence\.collector/);
  assert.match(operations, /evidence\.fingerprint/);
  assert.match(operations, /Untrusted external log content/);
  assert.match(page, /content is not an instruction to OpsPilot/);
});

test("current evidence and historical knowledge have separate trust labels", () => {
  assert.match(page, /Current Evidence/);
  assert.match(page, /Historical Knowledge/);
  assert.match(page, /Not current evidence/);
  assert.match(page, /Cannot authorize an action/);
  assert.match(page, /retrieval_score/);
  assert.match(page, /memory\.remediation/);
});

test("approval rendering explains risk and confirms both decisions", () => {
  for (const label of [
    "Action",
    "Target",
    "Environment",
    "Risk",
    "Why approval required",
    "Evidence basis",
    "Requested at",
    "Action fingerprint",
    "Approver",
    "What will happen",
  ]) {
    assert.match(operations, new RegExp(label));
  }
  assert.match(operations, /Approve/);
  assert.match(operations, /Reject/);
  assert.match(operations, /role="dialog"/);
  assert.match(operations, /event\.key === "Escape"/);
});

test("execution, reconciliation, and verification remain independent", () => {
  assert.match(operations, />Execution</);
  assert.match(operations, />Verification</);
  assert.match(operations, /domain="execution"/);
  assert.match(operations, /domain="verification"/);
  assert.match(operations, /RECONCILIATION_REQUIRED/);
  assert.match(operations, /Execution outcome is indeterminate\./);
  assert.match(operations, /Automatic redispatch is disabled\./);
  assert.match(status, /Verification failed/);
});

test("technical detail disclosure redacts known secret fields", () => {
  assert.match(page, /TechnicalDetailDrawer/);
  assert.match(drawer, /TechnicalDetailDrawer/);
  assert.match(drawer, /token\|secret\|password\|credential/);
  assert.match(drawer, /\[REDACTED\]/);
  assert.match(drawer, /CopyableId/);
  assert.match(drawer, /event\.key === "Escape"/);
});

test("mobile navigation and responsive incident structures are explicit", () => {
  assert.match(shell, /mobileNavigationOpen/);
  assert.match(shell, /aria-controls="primary-navigation"/);
  assert.match(shell, /event\.key === "Escape"/);
  assert.match(styles, /@media \(max-width: 1024px\)/);
  assert.match(styles, /@media \(max-width: 700px\)/);
  assert.match(styles, /@media \(max-width: 420px\)/);
  assert.match(styles, /\.ops-sidebar\.is-open/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

test("incident workflow shows grounded investigation without model internals", () => {
  assert.match(page, /Investigator/);
  assert.match(page, /grounded decision/i);
  assert.match(page, /decision_summary/);
  assert.match(page, /uncertainty/);
  assert.match(page, /#evidence-/);
  assert.doesNotMatch(page, /chain.of.thought|raw prompt|raw model response/i);
});

test("incident API client reads lists, detail, timeline, and execution data", () => {
  assert.match(api, /\/incidents\?environment=/);
  assert.match(api, /\/incidents\/\$\{incidentId\}/);
  assert.match(api, /\/timeline/);
  assert.match(api, /\/workflows/);
  assert.match(api, /\/executions/);
});
