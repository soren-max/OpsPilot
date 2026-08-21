from pathlib import Path

from app.memory.evaluation import OfflineRetrievalEvaluator, load_dataset

DATASET = Path(__file__).parents[3] / "evals/incident-memory/dataset.json"


def test_eval_dataset_and_dense_sparse_hybrid_benchmark() -> None:
    documents, queries = load_dataset(DATASET)
    assert 30 <= len(documents) <= 50
    assert len(queries) >= 10
    evaluator = OfflineRetrievalEvaluator(documents)
    results = {
        mode: evaluator.evaluate(queries, mode)
        for mode in ("dense", "sparse", "hybrid_rrf")
    }
    assert results["hybrid_rrf"].recall_at_5 >= 0.8
    assert results["hybrid_rrf"].recall_at_10 >= 0.9
    assert results["hybrid_rrf"].root_cause_hit_rate >= 0.9
