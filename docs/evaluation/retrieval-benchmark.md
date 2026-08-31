# Retrieval Benchmark

The M6 offline dataset contains 40 synthetic historical incident documents and 12 queries. Run
`make portfolio-benchmark` to regenerate Dense, Sparse, and Hybrid RRF metrics, including Recall@5,
Recall@10, MRR, root-cause hit rate, and per-query latency p50/p95.

No reranker row is shown because v1.0 has no reranker. The deterministic hash embedding makes the
dense baseline portable, not semantically equivalent to a hosted production embedding model. On
this intentionally lexical dataset sparse retrieval can outperform Hybrid RRF; hybrid is therefore
described as benchmarked, not universally superior.

The authoritative numbers are in `artifacts/portfolio-benchmark.json`. README values are checked
against that artifact by `scripts/check-portfolio-metrics.py`; latency is deliberately omitted from
README because it is host-sensitive.

