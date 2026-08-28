from __future__ import annotations

import json
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from app.deployment.models import DeploymentConfiguration


class UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key is forbidden: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def load_deployment_configuration(path: Path) -> DeploymentConfiguration:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("Deployment configuration must be a file")
    payload = yaml.load(resolved.read_text(encoding="utf-8"), Loader=UniqueKeySafeLoader)
    if not isinstance(payload, dict):
        raise ValueError("Deployment configuration must be a YAML object")
    # Validate with JSON semantics so YAML sequences map to immutable tuples while
    # strict scalar types and enum values remain enforced.
    return DeploymentConfiguration.model_validate_json(json.dumps(payload))


def resolve_operator_path(config_path: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if not path.is_absolute():
        path = config_path.resolve().parent / path
    return path.resolve()
