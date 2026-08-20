# Demo and Recording Guide

## Terminal demo

Install the locked backend environment, then run the deterministic scenario:

```bash
uv sync --project backend --extra dev --locked
make demo
```

Record only the command and its output. A terminal recorder such as `asciinema` is suitable; keep
recordings outside the repository or link to hosted media so large binaries do not enter Git.
Before recording, use a clean shell profile and confirm no credentials or private environment
values are visible. The checked-in reference transcript is
[`demo/expected-results/service-unavailable.txt`](../demo/expected-results/service-unavailable.txt).

## Frontend demo

The frontend is not required by the offline incident demo. For a UI walkthrough, start the local
development stack using the [Development Guide](development.md), use synthetic demo records, and
record the browser window only. Do not imply that the UI performs durable approval/resume; that is
M4 work. Avoid committing video, animated GIFs, or large screenshots.

## Architecture walkthrough

Open the [Architecture](architecture.md) Mermaid diagrams and narrate the boundaries from
Presentation to Adapters. Emphasize three independent responsibilities:

- LLM: reasoning only; it produces a grounded, structured proposal.
- Policy: deterministic authorization and approval requirements.
- Executor: executes only an already-authorized structured action.

The most useful sequence is: evidence collection → investigation → grounding → proposal → policy
→ `WAITING_APPROVAL`. Stop there. Durable checkpointing and resume belong to M4.

## Publication checklist

- Use only synthetic services, targets, tickets, logs, and metric values.
- Hide environment panels, shell history, notifications, and account details.
- Never show API keys, raw prompts, hidden reasoning, credentials, or internal hostnames.
- Prefer text transcripts and Mermaid source. If an image is essential, crop and compress a small
  PNG and verify it contains no private data.
