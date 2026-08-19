import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/api/client.ts", import.meta.url), "utf8");
const facade = await readFile(new URL("../src/api.ts", import.meta.url), "utf8");
const authContext = await readFile(new URL("../src/AuthContext.tsx", import.meta.url), "utf8");

test("API client safely handles empty and non-JSON responses", () => {
  assert.match(source, /response\.text\(\)/);
  assert.match(source, /content-type/);
  assert.match(source, /if \(!text\.trim\(\)\) return null/);
  assert.match(source, /服务暂时不可用，请稍后重试。/);
  assert.doesNotMatch(source, /await response\.json\(\)/);
});

test("API domains are split behind a compatibility facade", () => {
  for (const domain of ["auth", "catalog", "tasks", "audits", "system"]) {
    assert.match(facade, new RegExp(`api/${domain}`));
  }
  assert.match(facade, /Compatibility facade/);
});

test("permission failures remain visible while expired sessions fail closed", () => {
  assert.match(source, /response\.status === 401/);
  assert.doesNotMatch(source, /response\.status === 401 \|\| response\.status === 403/);
  assert.match(source, /new ApiError\(message, error\.request_id, error\.code, response\.status/);
});

test("stored sessions are revalidated after a page reload", () => {
  assert.match(authContext, /queryKey:\s*queryKeys\.auth\.me/);
  assert.match(authContext, /return await authApi\.me\(\)/);
  assert.doesNotMatch(authContext, /initialData:\s*null/);
});
