import argparse
from dataclasses import asdict
from pathlib import Path

from app.adapters.mcp.evaluation import evaluate, write_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MCP infrastructure contracts")
    parser.add_argument("--dataset", type=Path, default=Path("evals/mcp/contracts.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/mcp/results.json"))
    args = parser.parse_args()
    metrics = evaluate(args.dataset)
    write_results(metrics, args.output)
    print("Metric                                  Rate")
    for name, value in asdict(metrics).items():
        print(f"{name:<38} {value:.3f}")


if __name__ == "__main__":
    main()
