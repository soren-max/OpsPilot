import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../src/pages/IncidentsPage.tsx", import.meta.url), "utf8");
const api = await readFile(new URL("../src/api/incidents.ts", import.meta.url), "utf8");
const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");

test("incident UI exposes the durable lifecycle without a chat surface", () => {
  for (const section of [
    "Overview",
    "Evidence",
    "Hypotheses",
    "Diagnosis",
    "Actions",
    "Workflow",
    "Timeline",
  ]) {
    assert.match(page, new RegExp(section));
  }
  assert.doesNotMatch(page, /Chat|conversation|message composer/i);
  assert.match(app, /incidents\/:incidentId\?/);
});

test("incident API client reads lists, detail, and timeline", () => {
  assert.match(api, /\/incidents\?environment=/);
  assert.match(api, /\/incidents\/\$\{incidentId\}/);
  assert.match(api, /\/timeline/);
  assert.match(api, /\/workflows/);
});
