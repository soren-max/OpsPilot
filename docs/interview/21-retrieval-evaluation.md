# 21 — Retrieval Evaluation

Retrieval quality is measurable independently of diagnosis quality. M6 compares dense, sparse, and
Hybrid RRF using Recall@5, Recall@10, MRR, root-cause hit rate, and latency on a versioned synthetic
dataset. The dataset includes similar symptoms with different causes and different wording for the
same cause, making regressions visible before changing fusion or adding a reranker.
