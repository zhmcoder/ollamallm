"""Fetch model catalog from ollama.com (optional, with offline fallback)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from functools import lru_cache

from ollamallm.catalog.params import estimate_q4_gb, parse_params_b, size_gb_from_bytes, split_model_id
from ollamallm.models import ModelEntry

TIMEOUT = 8
TAGS_URL = "https://ollama.com/api/tags"
MODELS_URL = "https://ollama.com/v1/models"


def _get_json(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ollamallm/0.1"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _entry_from_id(model_id: str, size_bytes: int = 0) -> ModelEntry | None:
    name, tag = split_model_id(model_id)
    params = parse_params_b(tag)
    if size_bytes > 0:
        size_q4 = size_gb_from_bytes(size_bytes)
        if params is None and size_q4 > 0:
            params = round(size_q4 / 0.55, 2)
    elif params is not None:
        size_q4 = estimate_q4_gb(params)
    else:
        return None

    model_type = "moe" if "-a" in tag and "b-a" in tag else "dense"
    return ModelEntry(
        name=name,
        tag=tag,
        params_b=params or 0.0,
        size_q4_gb=size_q4,
        type=model_type,
    )


@lru_cache(maxsize=1)
def fetch_online_models() -> list[ModelEntry]:
    """Merge ollama.com API listings; empty list if offline."""
    by_id: dict[str, ModelEntry] = {}

    tags_data = _get_json(TAGS_URL)
    if isinstance(tags_data, dict):
        for item in tags_data.get("models", []):
            model_id = item.get("name") or item.get("model")
            if not model_id:
                continue
            entry = _entry_from_id(model_id, int(item.get("size") or 0))
            if entry:
                by_id[entry.full_name] = entry

    models_data = _get_json(MODELS_URL)
    if isinstance(models_data, dict):
        for item in models_data.get("data", []):
            model_id = item.get("id")
            if not model_id:
                continue
            entry = _entry_from_id(model_id)
            if entry:
                by_id.setdefault(entry.full_name, entry)

    return list(by_id.values())
