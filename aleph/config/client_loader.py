from __future__ import annotations

import json
from pathlib import Path


def _load_yaml(path: Path) -> object:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "YAML client blueprint loading requires PyYAML. Install the 'service' extra to enable it."
        ) from exc
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_client_blueprints(path: str | Path) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Client blueprint config '{file_path}' does not exist.")

    suffix = file_path.suffix.lower()
    if suffix == ".json":
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    elif suffix in {".yaml", ".yml"}:
        payload = _load_yaml(file_path)
    else:
        raise ValueError(f"Unsupported client blueprint file format '{suffix}'.")

    if isinstance(payload, dict):
        payload = payload.get("clients", [])
    if not isinstance(payload, list):
        raise ValueError("Client blueprint config must resolve to a list of client definitions.")
    return payload


def register_client_blueprints(engine, path: str | Path) -> list[dict]:
    definitions = load_client_blueprints(path)
    return [engine.register_client(definition) for definition in definitions]
