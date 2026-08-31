import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.memory.evaluation import OfflineRetrievalEvaluator, load_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate historical incident retrieval")
    parser.add_argument(
        "--dataset", default="evals/incident-memory/dataset.json", type=Path
    )
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    documents, queries = load_dataset(args.dataset)
    evaluator = OfflineRetrievalEvaluator(documents)
    results = tuple(evaluator.evaluate(queries, mode) for mode in ("dense", "sparse", "hybrid_rrf"))
    print("Retriever       Recall@5  Recall@10  MRR    RC Hit  p50 ms  p95 ms")
    for item in results:
        print(
            f"{item.retriever:<15} {item.recall_at_5:>8.3f}  {item.recall_at_10:>9.3f}  "
            f"{item.mrr:>5.3f}  {item.root_cause_hit_rate:>6.3f}  "
            f"{item.latency_p50_ms:>6.3f}  {item.latency_p95_ms:>6.3f}"
        )
    if args.json_output:
        args.json_output.write_text(
            json.dumps([asdict(item) for item in results], indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
