"""Fetch model catalog from ollama.com (optional, with offline fallback)."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from ollamallm.catalog.params import estimate_q4_gb, parse_params_b, size_gb_from_bytes, split_model_id
from ollamallm.models import ModelEntry

TIMEOUT = 12
NETWORK_RETRY_COUNT = 2  # 首次失败后重试 2 次
TAGS_URL = "https://ollama.com/api/tags"
MODELS_URL = "https://ollama.com/v1/models"
SEARCH_URL = "https://ollama.com/search"
LIBRARY_URL = "https://ollama.com/library"
USER_AGENT = "ollamallm/0.1"
SEARCH_MODEL_LIMIT = 12
SEARCH_WORKERS = 4
SEARCH_TAGS_PER_MODEL = 8

_PARAM_SPAN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([kmbt])\b", re.I)
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([GTMK]B)", re.I)
_SEARCH_CARD_RE = re.compile(r'href="/library/([^"/]+)" class="group w-full"')
_SEARCH_TITLE_RE = re.compile(r'x-test-search-response-title>([^<]+)<')

_api_model_sizes_cache: dict[str, list[tuple[str, int]]] | None = None
_api_load_ok: bool | None = None


@dataclass
class SearchOutcome:
    models: list[ModelEntry]
    network_error: bool = False


def _get_json(url: str) -> dict | list | None:
    for attempt in range(NETWORK_RETRY_COUNT + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            if attempt < NETWORK_RETRY_COUNT:
                time.sleep(0.5 * (attempt + 1))
    return None


def _get_html(url: str) -> str | None:
    for attempt in range(NETWORK_RETRY_COUNT + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode()
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < NETWORK_RETRY_COUNT:
                time.sleep(0.5 * (attempt + 1))
    return None


def _parse_param_span(text: str) -> float | None:
    match = _PARAM_SPAN_RE.search(text.strip())
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "k":
        return round(value / 1_000_000, 4)
    if unit == "m":
        return round(value / 1_000, 3)
    if unit == "t":
        return value * 1000
    return value


def _parse_size_gb(text: str) -> float:
    match = _SIZE_RE.search(text.strip())
    if not match:
        return 0.0
    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "MB":
        return round(value / 1024, 2)
    if unit == "KB":
        return round(value / (1024**2), 3)
    if unit == "TB":
        return round(value * 1024, 2)
    return round(value, 2)


def _capability_to_type(capabilities: list[str]) -> str:
    joined = " ".join(capabilities).lower()
    if "rerank" in joined:
        return "rerank"
    if "embed" in joined:
        return "embed"
    if "vision" in joined:
        return "vision"
    if "thinking" in joined:
        return "thinking"
    return "dense"


def _entry_from_id(model_id: str, size_bytes: int = 0, *, model_type: str = "dense") -> ModelEntry | None:
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

    if model_type == "dense" and "-a" in tag and "b-a" in tag:
        model_type = "moe"
    return ModelEntry(
        name=name,
        tag=tag,
        params_b=params or 0.0,
        size_q4_gb=size_q4,
        type=model_type,
    )


def _parse_search_page(html: str) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()

    def add(name: str, chunk: str) -> None:
        if name in seen or "/" in name:
            return
        seen.add(name)
        capabilities = re.findall(r"x-test-capability[^>]*>([^<]+)", chunk)
        size_match = re.search(r"x-test-size[^>]*>([^<]+)", chunk)
        results.append(
            {
                "name": name,
                "capabilities": capabilities,
                "model_type": _capability_to_type(capabilities),
                "params_b": _parse_param_span(size_match.group(1)) if size_match else None,
            }
        )

    for match in _SEARCH_CARD_RE.finditer(html):
        add(match.group(1), html[match.start() : match.start() + 2500])

    if not results:
        for match in _SEARCH_TITLE_RE.finditer(html):
            name = match.group(1).strip()
            add(name, html[match.start() : match.start() + 2500])

    return results


def _api_model_sizes() -> dict[str, list[tuple[str, int]]]:
    global _api_model_sizes_cache, _api_load_ok
    if _api_model_sizes_cache is not None:
        return _api_model_sizes_cache

    data = _get_json(TAGS_URL)
    if not isinstance(data, dict):
        _api_load_ok = False
        return {}

    grouped: dict[str, list[tuple[str, int]]] = {}
    for item in data.get("models", []):
        model_id = item.get("name") or item.get("model")
        if not model_id:
            continue
        base_name, _ = split_model_id(model_id)
        grouped.setdefault(base_name, []).append((model_id, int(item.get("size") or 0)))

    _api_model_sizes_cache = grouped
    _api_load_ok = True
    return grouped


def _models_from_api_for_name(name: str, *, model_type: str) -> list[ModelEntry]:
    entries: list[ModelEntry] = []
    for model_id, size_bytes in _api_model_sizes().get(name.lower(), []):
        entry = _entry_from_id(model_id, size_bytes, model_type=model_type)
        if entry and entry.size_q4_gb > 0:
            entries.append(entry)
    return entries


def _search_candidates_from_api(keyword: str) -> list[dict]:
    key = keyword.lower().strip()
    seen: set[str] = set()
    candidates: list[dict] = []

    for base_name, items in _api_model_sizes().items():
        if key not in base_name and not any(key in model_id.lower() for model_id, _ in items):
            continue
        if base_name in seen:
            continue
        seen.add(base_name)
        candidates.append(
            {
                "name": base_name,
                "capabilities": [],
                "model_type": "dense",
                "params_b": None,
            }
        )
        if len(candidates) >= SEARCH_MODEL_LIMIT:
            break

    return candidates


def _limit_tag_entries(entries: list[ModelEntry]) -> list[ModelEntry]:
    if len(entries) <= SEARCH_TAGS_PER_MODEL:
        return entries

    def rank(entry: ModelEntry) -> tuple[int, str]:
        tag = entry.tag.lower()
        if tag == "latest":
            return (0, tag)
        if re.search(r"-q\d", tag):
            return (3, tag)
        return (1, tag)

    entries.sort(key=rank)
    return entries[:SEARCH_TAGS_PER_MODEL]


def _fetch_model_tags(name: str, *, model_type: str, fallback_params: float | None) -> list[ModelEntry]:
    by_tag: dict[str, ModelEntry] = {}

    for entry in _models_from_api_for_name(name, model_type=model_type):
        by_tag[entry.tag] = entry

    if not by_tag:
        html = _get_html(f"{LIBRARY_URL}/{urllib.parse.quote(name)}/tags")
        if html:
            for block in re.split(r"group px-4 py-3", html)[1:]:
                tag_match = re.search(rf'/library/{re.escape(name)}:([^"\s]+)"', block)
                if not tag_match:
                    continue
                tag = tag_match.group(1)
                size_match = _SIZE_RE.search(block)
                size_q4 = _parse_size_gb(size_match.group(0)) if size_match else 0.0
                params = parse_params_b(tag) or fallback_params
                if size_q4 <= 0 and params:
                    size_q4 = estimate_q4_gb(params)
                if params is None and size_q4 > 0:
                    params = round(size_q4 / 0.55, 3)
                if size_q4 <= 0:
                    continue
                by_tag[tag] = ModelEntry(
                    name=name,
                    tag=tag,
                    params_b=params or 0.0,
                    size_q4_gb=size_q4,
                    type=model_type,
                )

    if by_tag:
        return _limit_tag_entries(list(by_tag.values()))

    params = fallback_params or 0.0
    size_q4 = estimate_q4_gb(params) if params else 0.0
    return [ModelEntry(name=name, tag="latest", params_b=params, size_q4_gb=size_q4, type=model_type)]


def _search_ollama_library_once(keyword: str) -> SearchOutcome:
    """Single attempt to search ollama.com."""
    key = keyword.lower().strip()
    if not key:
        return SearchOutcome(models=[])

    search_page_failed = False
    candidates: list[dict] = []
    html = _get_html(f"{SEARCH_URL}?q={urllib.parse.quote(keyword.strip())}")
    if html:
        parsed = _parse_search_page(html)
        matched = [item for item in parsed if key in item["name"].lower()]
        candidates = matched or parsed
    else:
        search_page_failed = True

    if not candidates:
        _api_model_sizes()
        candidates = _search_candidates_from_api(keyword)

    if not candidates:
        api_failed = _api_load_ok is False
        if search_page_failed and (api_failed or _api_load_ok is None):
            return SearchOutcome(models=[], network_error=True)
        return SearchOutcome(models=[])

    entries: dict[str, ModelEntry] = {}
    with ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as pool:
        futures = [
            pool.submit(
                _fetch_model_tags,
                item["name"],
                model_type=item["model_type"],
                fallback_params=item["params_b"],
            )
            for item in candidates[:SEARCH_MODEL_LIMIT]
        ]
        for future in as_completed(futures):
            try:
                for entry in future.result():
                    entries[entry.full_name] = entry
            except Exception:
                continue

    models = list(entries.values())
    models.sort(key=lambda m: (m.name, m.tag))
    if not models and search_page_failed:
        return SearchOutcome(models=[], network_error=True)
    return SearchOutcome(models=models)


def search_ollama_library(keyword: str) -> SearchOutcome:
    """Search ollama.com model library; retry on network errors."""
    last = SearchOutcome(models=[], network_error=True)
    for attempt in range(NETWORK_RETRY_COUNT + 1):
        last = _search_ollama_library_once(keyword)
        if last.models or not last.network_error:
            return last
        if attempt < NETWORK_RETRY_COUNT:
            time.sleep(0.8 * (attempt + 1))
    return last


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
