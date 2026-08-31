# Portfolio v1.0 Benchmark

This is the evidence index for the stable OpsPilot Portfolio v1.0 release. It adds evaluation and
release evidence; it does not introduce an M9 feature or change the authorization architecture.

Run the offline benchmark from the repository root:

```bash
make portfolio-benchmark
# equivalent
uv run --project backend --no-sync python -m app.evaluation.portfolio
```

The command requires no OpenAI key, Harness SaaS account, remote MCP server, or company network. It
re-executes deterministic investigation fixtures, the M6 retrieval dataset, the M7 MCP dataset, and
the contract tests behind the safety, workflow, execution, and compatibility matrices. It writes:

- `artifacts/portfolio-benchmark.json` — schema-validated machine-readable result.
- `artifacts/portfolio-benchmark.md` — human-readable result from the same in-memory object.

Each artifact records source commit, dirty state, UTC timestamp, Python version, dataset and scenario
versions, and configuration mode. Secrets, tokens, raw prompts, and hidden reasoning are excluded.
Latency is measured, not copied into permanent prose; compare latency only on like-for-like hosts.

## Categories

| Category | Evidence |
| --- | --- |
| Incident investigation | Six M3B cases; deterministic baseline by default; real LLM is `NOT RUN` unless separately executed |
| Retrieval | Dense, sparse, and Hybrid RRF over the checked-in M6 dataset |
| Safety | Fifteen adversarial paths mapped to executable controls |
| Workflow reliability | Approval/restart/idempotency/checkpoint matrix |
| Execution reliability | Dispatch, UNKNOWN, reconciliation, and verification matrix |
| MCP contract | Seven rates recomputed from the M7 dataset |
| Demo reproducibility | Three recorded `make demo-local` lifecycles |
| Performance | Retrieval p50/p95 and demo lifecycle p50/max with sample size |

Run `make portfolio-demo-repeatability` to populate three live synthetic demo runs, rerun the
benchmark, then run `make portfolio-check`. A category can say `NOT RUN`; the runner never replaces
missing execution with invented numbers.

The checked-in three-run sample records lifecycle p50 and max in the artifact. Run #1 includes a
cold Docker image build/pull; later runs use the same `make demo-local` entrypoint with local cache.
The sample size is exactly 3, so these timings describe demo predictability on one host, not a
performance distribution or production SLO.

Related detail: [safety matrix](safety-matrix.md), [reliability matrix](reliability-matrix.md),
[retrieval benchmark](retrieval-benchmark.md), [legacy compatibility](legacy-compatibility.md), and
[limitations](limitations.md).
