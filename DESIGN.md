# OpsPilot Operations Design System

This document is the canonical visual and interaction contract for OpsPilot. The system is informed by enterprise developer-tool patterns, not by any single brand. It applies to product UI only; marketing pages may define a separate contract.

## Visual Theme

OpsPilot is operational, technical, calm, precise, trustworthy, dense but readable, and safety-aware. It should look like a console an engineer can keep open throughout an incident.

The visual foundation follows a flat enterprise model: neutral surfaces, charcoal text, one blue product accent, semantic status colors, a 4px spacing grid, low radii, thin borders, and minimal shadows. Product identity comes from information structure and governed-operation semantics rather than decoration.

## Design Principles

1. **State before decoration.** Show current state, risk, evidence, ownership, and the safe next action before secondary detail.
2. **Facts over synthetic insight.** Do not invent metrics, trends, scores, SLAs, or AI confidence that the backend does not provide.
3. **Operational distinctions stay distinct.** Current evidence is not historical knowledge. Execution success is not verification success. `UNKNOWN` is not failure. Approval is not execution.
4. **One product language.** Reuse semantic tokens and primitives. Do not create a new visual dialect for each page.
5. **Density with hierarchy.** Prefer sections, dividers, tables, metadata grids, and disclosure over card grids and oversized whitespace.
6. **Safety is visible.** Environment, target, backend, profile, policy, approval reason, and action fingerprint must be easy to identify.
7. **Technical detail is available, not dominant.** Keep raw payloads, provenance, identifiers, and logs in consistent disclosure surfaces.
8. **No brand cloning.** Do not copy logos, product marks, proprietary fonts, distinctive illustrations, or signature brand colors from reference products.

## Design Sources

- **Enterprise foundation (~60%):** Carbon-style 4px rhythm, restrained neutral palette, blue accent, flat surfaces, hairline separation, dense tables, and strong accessibility.
- **Interaction polish (~20%):** precise hover/focus states, keyboard-friendly navigation, compact metadata, calm dark surfaces, and command-oriented interaction.
- **Incident UX (~10%):** incident prioritization, evidence hierarchy, timeline readability, and technical metadata presentation.
- **Infrastructure UX (~10%):** explicit environment, target, execution backend, profile, and operator-owned configuration identity.

These percentages describe design principles, not copied code or branding.

## Color Roles

All implementation colors must be referenced through semantic tokens in `frontend/src/design-tokens.css`.

| Role | Light | Meaning |
| --- | --- | --- |
| Canvas | `#f4f4f4` | Application background |
| Surface | `#ffffff` | Primary content and chrome |
| Subtle surface | `#f8f8f8` | Secondary bands and technical metadata |
| Border | `#e0e0e0` | Hairlines and section boundaries |
| Text | `#161616` | Primary content |
| Secondary text | `#525252` | Metadata and supporting copy |
| Product accent | `#0f62fe` | Primary action, link, active navigation, focus |
| Success | `#198038` | Completed, healthy, approved, resolved |
| Warning | `#8e6a00` | Waiting, degraded, indeterminate, reconciliation |
| Danger | `#da1e28` | Confirmed failure, rejection, critical risk |
| Unknown | `#6f6f6f` | Missing or unconnected information |

Semantic colors are scarce and never decorative. Status must always include a text label and, where practical, an icon in addition to color.

## Status Semantics

Use a single semantic vocabulary across domains:

- `SUCCESS`: completed, approved, healthy, resolved, or verified.
- `INFO`: active investigation, running work, or non-risk informational state.
- `WARNING`: waiting, degraded, timed out, indeterminate outcome, or reconciliation required.
- `DANGER`: confirmed failure, rejection, unhealthy state, or critical severity.
- `NEUTRAL`: inactive, cancelled, skipped, or ordinary metadata.
- `UNKNOWN`: absent, not connected, or not yet observed.

Domain labels remain explicit: `APPROVED`, `RESOLVED`, `SUCCEEDED`, and `VERIFIED` may share success semantics but must not be collapsed into the same business meaning.

`UNKNOWN` and `RECONCILIATION_REQUIRED` use warning/technical treatment, never a generic red failure treatment. Pair them with: “Execution outcome is indeterminate. Automatic redispatch is disabled.”

## Typography

Use the system sans stack for all UI. Use the semantic monospace stack only for identifiers, fingerprints, provider references, trace IDs, configuration keys, commands, and logs. Do not require proprietary fonts.

The hierarchy is compact:

- Page title: 24–28px, semibold, short.
- Section title: 16–18px, semibold.
- Panel/card title: 14–16px, semibold.
- Body: 14px on dense product surfaces; 16px for explanatory copy.
- Metadata and caption: 12–13px with sufficient contrast.
- Mono identifier: 12–13px, never smaller than 11px.

Avoid marketing-scale headings, decorative all-caps paragraphs, and low-contrast fine print.

## Spacing, Radius, and Elevation

- Base spacing unit: 4px. Prefer existing `--opspilot-space-*` tokens.
- Default section gap: 16–24px. Default compact control gap: 8px.
- Default content padding: 16–24px. Do not use 32–48px padding for routine cards.
- Radius: 2–6px for controls and panels; pill radius only for compact status badges.
- Elevation: flat by default. Use borders and surface changes for hierarchy.
- Shadows are reserved for drawers, dialogs, menus, and other overlays.
- Motion duration: 120–180ms. Respect `prefers-reduced-motion`.

## Layout and App Shell

Every authenticated route uses the shared `AppShell`:

- `Sidebar`: persistent on desktop, compact on tablet, drawer on mobile.
- `TopBar`: global environment identity, execution capability, theme, and user controls.
- `Breadcrumbs`: between global chrome and page content.
- `PageHeader`: title, short task-oriented description, and page-level actions.
- `ContentContainer`: shared dashboard/data/config width tiers.
- `GlobalStatusArea`: network and execution-boundary status without obstructing content.

Primary navigation reflects real product value: Overview, Incidents, Executions, Audit, Services, Hosts, Capabilities, and Settings. Do not add a route for an unimplemented feature. MCP remains an interoperability detail unless it gains a real user workflow.

## Navigation

- Use stable nouns and operator language.
- The active route must be visible without relying only on color.
- Mobile navigation is a labeled drawer with Escape and backdrop dismissal.
- Keyboard focus moves to main content after route changes.
- Command palettes, when present, navigate or search only. They never trigger remediation.

## Tables and Filters

- Tables are medium-dense with sticky or visually persistent headers where useful.
- Primary entity identity appears in the first important column and links to detail.
- Search and high-value filters sit in one `FilterBar`; include a result count and clear action.
- Loading uses skeleton structure, not a blank screen. Empty and error states explain what is absent and the next safe action.
- On narrow screens, hide lower-priority columns or provide a detail view. Do not compress every desktop column into 390px.
- Interactive rows require an accessible link and visible keyboard focus.

## Forms and Governed Actions

- Every control has a visible label or accessible name.
- Help and validation text sit near the related control.
- Disabled actions explain why when the policy result is available.
- Confirmation dialogs state what will happen, target, environment, risk, backend implications, and whether approval is required.
- Approve and Reject include icon, label, and semantic state. Color alone is insufficient.

## Incident UX

The Incident detail is the product’s primary demonstration surface.

The header exposes title, severity, status, service, environment, created/updated time, and workflow state. The page then uses an `Incident Lifecycle` rail linking to:

`Observe → Investigate → Diagnose → Policy → Approval → Execute → Verify`

Each lifecycle step is one of `COMPLETE`, `ACTIVE`, `WAITING`, `FAILED`, or `SKIPPED`. Sections appear in the same conceptual order, while the highest-risk active section may receive additional emphasis.

### Evidence

Evidence is typed as Metric, Log, Ticket, or Service Status with a consistent icon and label. Show source, observed time, summary, collector/provenance, and short fingerprint. Raw excerpts and metadata open in the technical-detail drawer.

Logs are untrusted observations. Prompt-like or malicious text remains ordinary log evidence and is never styled as an instruction.

### Diagnosis and Historical Knowledge

Diagnosis shows root cause, confidence, supporting evidence, and contributing factors. Evidence links resolve to current incident evidence.

Related incidents live in a separate `Historical context` section labeled “Not current evidence.” Show retrieval context, service, environment, root cause, resolution, resolved time, and source. Retrieved knowledge cannot authorize an action.

### Timeline

Timeline entries show timestamp, event type, actor/system, summary, and bounded safe metadata. Raw audit JSON stays in technical detail disclosure.

## Approval UX

The `Approval Decision Panel` shows action, target, environment, risk, why approval is required, evidence basis, requested time, action fingerprint, and approver state.

Before either decision, a confirmation dialog restates what will happen, target, environment, risk, and decision consequence. Approval does not bypass policy; rejection prevents execution of that request.

## Execution and Verification UX

Execution displays status, backend, profile, submitted/started/finished time, duration, provider reference, attempt, reconciliation status, and trace identity. Verification is a separate adjacent state with its own label.

`Execution: SUCCEEDED` plus `Verification: FAILED` is a valid and important result. Never summarize it as green success.

For `UNKNOWN` or `RECONCILIATION_REQUIRED`, show last reconciliation, provider reference, automatic redispatch disabled, and the next safe action. Use neutral/warning technical semantics.

## Technical Content

Use `TechnicalDetailDrawer` for raw evidence, execution detail, audit metadata, MCP provenance, and trace identifiers. Drawers manage focus, close on Escape, and restore the invoking control’s focus.

Use `CopyableId` for identifiers. Never render known secret fields such as tokens, passwords, credentials, authorization headers, cookies, or private keys. Sanitize metadata before rendering.

## Dark Mode

Dark mode uses the same token roles and hierarchy. It is not a mechanical inversion:

- Canvas and surface levels remain distinguishable.
- Text uses off-white and calibrated secondary gray, not pure-white everywhere.
- Severity and focus indicators meet contrast expectations.
- Terminal surfaces remain distinct from ordinary panels.
- Semantic meaning and component structure match light mode.

## Responsive Behavior

Review at 1440, 1280, 1024, 768, and 390px.

- Desktop: persistent labeled sidebar and wide operational tables.
- Laptop: compact gaps and selective secondary metadata.
- Tablet: compact/collapsible navigation and reduced table columns.
- Narrow/mobile: navigation drawer, stacked metadata, shortened table columns, and full-width drawers/dialogs.
- Minimum usable touch target is 40px, with 44px preferred on touch-first layouts.

## Accessibility

- Use semantic landmarks, headings, lists, tables, buttons, links, labels, and native controls.
- Provide visible `:focus-visible` treatment using the primary token.
- Dialogs and drawers trap focus, close with Escape, and restore focus.
- Maintain logical DOM and tab order.
- Do not communicate status, severity, selected state, or risk by color alone.
- Honor reduced motion and forced/height-constrained viewport behavior.
- Review text, buttons, focus rings, badges, and selected table rows for WCAG contrast.

## Do

- Reuse semantic tokens and existing primitives.
- Make environment, target, backend, and profile visible.
- Keep current evidence and historical context visibly separate.
- Separate execution, reconciliation, and verification states.
- Prefer sections, dividers, tables, and disclosure.
- Use real backend data and honest unknown states.

## Don’t

- Do not use glass blur, neon cyberpunk styling, large gradients, background blobs, or decorative AI purple.
- Do not wrap every metric or field in a large rounded card.
- Do not create fake operational metrics or charts.
- Do not copy another company’s logo, assets, fonts, illustrations, or signature palette.
- Do not dump raw JSON into the primary reading flow.
- Do not make destructive or governed operations available through navigation shortcuts.

## Agent Implementation Guide

Before changing frontend UI:

1. Read this `DESIGN.md` and any applicable `AGENTS.md`.
2. Inspect frontend architecture, routes, data contracts, primitives, and CSS ownership.
3. Preserve semantic design tokens and the existing product identity.
4. Reuse existing primitives; introduce only recurring semantic components.
5. Validate loading, empty, error, hover, focus, disabled, and active states.
6. Review keyboard behavior, accessible names, contrast, and non-color semantics.
7. Review light and dark themes at 390, 768, 1024, 1280, and 1440px.
8. Run `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`, and `npm run format:check` in `frontend/`.
9. Report visual-review coverage, data-contract limitations, and any deferred migration work.

## CSS Migration Boundary

The intended dependency direction is:

`design-tokens.css → shared primitives → feature styles`

`styles.css` and `reference-console.css` contain frozen compatibility selectors from earlier iterations. Do not add new feature-specific rules there. New product work belongs in `operations-console.css` until those compatibility layers can be removed through verified, incremental migration. Temporary aliases in `design-tokens.css` must resolve to canonical `--opspilot-*` tokens and must not introduce independent values.
