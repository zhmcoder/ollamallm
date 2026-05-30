"""Load embedded catalog JSON files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ollamallm.catalog.online import fetch_online_models
from ollamallm.models import ModelEntry


def _catalog_path(name: str) -> Path:
    return Path(__file__).parent / "catalog" / name


@lru_cache(maxsize=8)
def load_json(name: str) -> list | dict:
    path = _catalog_path(name)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _load_builtin_models() -> list[ModelEntry]:
    raw = load_json("models.json")
    return [ModelEntry(**item) for item in raw]


def load_models(*, include_online: bool = True) -> list[ModelEntry]:
    """Merge built-in catalog with ollama.com listings (when online)."""
    merged: dict[str, ModelEntry] = {}
    for entry in _load_builtin_models():
        merged[entry.full_name] = entry

    online_count = 0
    if include_online:
        for entry in fetch_online_models():
            merged[entry.full_name] = entry
            online_count += 1

    models = list(merged.values())
    models.sort(key=lambda m: (m.params_b, m.name, m.tag))
    return models


def catalog_stats(models: list[ModelEntry] | None = None) -> tuple[int, int]:
    models = models or load_models()
    online = fetch_online_models()
    return len(models), len(online)


def load_mac_specs() -> list[dict]:
    return load_json("mac_specs.json")


def load_mac_intel_specs() -> list[dict]:
    return load_json("mac_intel_specs.json")


def load_mac_model_ids() -> list[dict]:
    return load_json("mac_model_ids.json")


def load_gpu_specs() -> list[dict]:
    return load_json("gpu_specs.json")
