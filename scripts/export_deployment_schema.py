import json
from pathlib import Path

from app.deployment.models import DeploymentConfiguration

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "deployment/schemas/deployment-profile.schema.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(DeploymentConfiguration.model_json_schema(), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
