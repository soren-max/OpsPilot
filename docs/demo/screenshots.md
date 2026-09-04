# OpsPilot Portfolio Screenshots

Use only the synthetic scenarios shipped in `demo/incidents/` and the local lab. Never capture credentials, private inventory, production hostnames, access tokens, or personal data.

## Canonical setup

1. Start the documented local demo with `make demo-local` from the repository root.
2. Open the URL printed by the demo command and sign in with the documented local demo identity.
3. Select the synthetic environment used by the service-unavailable scenario.
4. Set browser zoom to 100%, viewport to 1440 × 1000, and theme to Light unless the shot specifically calls for Dark.
5. Open **Incidents** and follow the highlighted **Portfolio demo path**. Wait until visible loading states settle before capture.
6. Keep the browser window, route, scenario, theme, and viewport consistent across recaptures.

Store local captures outside the repository or in a review artifact. Do not commit large screenshot binaries as a substitute for regression tests.

## Recommended set

### 1. Incident Overview

- Route: `/incidents/<synthetic-service-down-id>`
- Viewport: 1440 × 1000, Light
- Frame: page header, incident identity, and the complete Incident Lifecycle rail.
- Demonstrates: severity/status, service/environment identity, workflow state, and demo readability.
- Suggested filename: `01-incident-overview-light.png`

### 2. Evidence + Diagnosis

- Route: same incident, `#diagnosis`
- Viewport: 1440 × 1000, Light
- Frame: typed Evidence cards, Current Evidence boundary, Diagnosis, and the first Historical Context item.
- Demonstrates: provenance, untrusted log treatment, supporting evidence, confidence, and “Not current evidence” separation.
- Suggested filename: `02-evidence-diagnosis-light.png`

### 3. Approval

- Route: same incident, `#approval`
- Viewport: 1280 × 900, Dark
- Frame: Approval Decision Panel with action, target, environment, risk, evidence basis, fingerprint, and Approve/Reject controls. If safe, open the confirmation dialog without submitting.
- Demonstrates: governed action boundary, consequence preview, keyboard-ready modal, and dark-mode hierarchy.
- Suggested filename: `03-approval-dark.png`

### 4. Execution + Verification Timeline

- Route: same incident, `#execution`
- Viewport: 1440 × 1000, Dark
- Frame: separate Execution and Verification outcomes, Backend/Profile, reconciliation data, and the start of Timeline/Audit.
- Prefer a synthetic state where Execution is `SUCCEEDED` and Verification is `FAILED`, or an `UNKNOWN`/`RECONCILIATION_REQUIRED` fixture when available.
- Demonstrates: outcome separation, indeterminate-state safety, provider identity, and event observability.
- Suggested filename: `04-execution-verification-dark.png`

## Responsive review captures

These are review artifacts rather than portfolio images:

| Width | Required check |
| ---: | --- |
| 390 | Mobile navigation drawer, stacked identity, compact incident table, full-width technical drawer |
| 768 | Horizontal lifecycle rail, stacked evidence/knowledge, usable approval controls |
| 1024 | Compact sidebar, reduced incident columns, two-column operational content where space permits |
| 1280 | Laptop density, filter wrapping, incident and execution metadata |
| 1440 | Canonical portfolio composition |

Repeat one canonical frame in both themes. Confirm visible focus, status icons and labels, contrast, and that no state relies on color alone.

## Recapture checklist

- Synthetic data only.
- No browser extensions, notifications, debug overlays, or devtools in frame.
- No clipped drawer, tooltip, dropdown, or focus ring.
- No loading skeleton unless the state itself is under review.
- No raw secret fields in Technical Detail.
- Execution and Verification remain separately readable.
- Historical Context visibly says “Not current evidence.”
- Filenames and crop remain stable so reviewers can compare captures manually.
