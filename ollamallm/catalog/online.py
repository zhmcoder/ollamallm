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
SEARCH_PAGE_COUNT = 3
SEARCH_MODEL_LIMIT = 60  # 约 3 页 × 20 条/页
SEARCH_WORKERS_BASE = 4
SEARCH_WORKERS_MAX = 16
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
    has_more_results: bool = False


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
        name = name.strip()
        if not name or name in seen:
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

    for match in _SEARCH_TITLE_RE.finditer(html):
        add(match.group(1).strip(), html[match.start() : match.start() + 2500])

    return results


def _model_tags_url(name: str) -> str:
    if "/" in name:
        return f"https://ollama.com/{name}/tags"
    return f"{LIBRARY_URL}/{urllib.parse.quote(name)}/tags"


def _tag_href_patterns(name: str) -> list[str]:
    escaped = re.escape(name)
    if "/" in name:
        return [rf"/{escaped}:([^\"\s]+)\""]
    return [rf'/library/{escaped}:([^"\s]+)"']


def _search_page_url(keyword: str, page: int) -> str:
    q = urllib.parse.quote(keyword.strip())
    if page <= 1:
        return f"{SEARCH_URL}?q={q}"
    return f"{SEARCH_URL}?page={page}&q={q}"


def _has_next_search_page(html: str, current_page: int) -> bool:
    return f"page={current_page + 1}" in html


def _search_tag_workers(candidate_count: int) -> int:
    """Scale tag-fetch concurrency when multi-page search returns many models."""
    if candidate_count <= 12:
        return SEARCH_WORKERS_BASE
    return min(SEARCH_WORKERS_MAX, max(8, (candidate_count + 4) // 5))


def _fetch_single_search_page(keyword: str, page: int) -> tuple[int, str | None]:
    return page, _get_html(_search_page_url(keyword, page))


def _fetch_search_pages(keyword: str) -> tuple[list[dict], bool, bool]:
    """Fetch up to SEARCH_PAGE_COUNT pages in parallel; return (merged, has_more, all_pages_failed)."""
    page_html: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=SEARCH_PAGE_COUNT) as pool:
        futures = [
            pool.submit(_fetch_single_search_page, keyword, page)
            for page in range(1, SEARCH_PAGE_COUNT + 1)
        ]
        for future in as_completed(futures):
            page, html = future.result()
            if html:
                page_html[page] = html

    seen: set[str] = set()
    merged: list[dict] = []
    for page in range(1, SEARCH_PAGE_COUNT + 1):
        html = page_html.get(page)
        if not html:
            continue
        for item in _parse_search_page(html):
            name = item["name"]
            if name in seen:
                continue
            seen.add(name)
            merged.append(item)

    final_page_html = page_html.get(SEARCH_PAGE_COUNT)
    has_more = bool(final_page_html and _has_next_search_page(final_page_html, SEARCH_PAGE_COUNT))
    return merged, has_more, not page_html


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


def _search_candidates_from_api(keyword: str) -> tuple[list[dict], bool]:
    key = keyword.lower().strip()
    seen: set[str] = set()
    candidates: list[dict] = []
    has_more = False

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
            has_more = True
            break

    return candidates, has_more


_TAG_VARIANT_RE = re.compile(r"-(q\d|fp\d|bf16|mlx|qat|mxfp\d|nvfp\d|int\d|gguf)", re.I)


def _limit_tag_entries(entries: list[ModelEntry]) -> list[ModelEntry]:
    if len(entries) <= SEARCH_TAGS_PER_MODEL:
        return entries

    def rank(entry: ModelEntry) -> tuple[int, float, str]:
        tag = entry.tag.lower()
        if tag == "latest":
            group = 0
        elif "-" not in tag or re.fullmatch(r"\d+(?:\.\d+)?x?\d*b-a\d+(?:\.\d+)?b", tag):
            # Canonical size tags: e2b, 12b, 31b, 26b-a4b ...
            group = 1
        elif _TAG_VARIANT_RE.search(tag):
            group = 3
        else:
            group = 2
        # Prefer smaller (more installable) within a group.
        return (group, entry.size_q4_gb or 0.0, tag)

    entries.sort(key=rank)
    return entries[:SEARCH_TAGS_PER_MODEL]


def _is_cloud_tag(tag: str) -> bool:
    """Cloud tags run on Ollama's servers and have no local download size."""
    t = tag.lower()
    return t == "cloud" or t.endswith("-cloud") or t.startswith("cloud-") or "-cloud-" in t


def _parse_tags_from_html(
    name: str, html: str, *, model_type: str, fallback_params: float | None
) -> dict[str, ModelEntry]:
    by_tag: dict[str, ModelEntry] = {}
    tag_patterns = _tag_href_patterns(name)
    for block in re.split(r"group px-4 py-3", html)[1:]:
        tag = None
        for pattern in tag_patterns:
            tag_match = re.search(pattern, block)
            if tag_match:
                tag = tag_match.group(1)
                break
        if not tag or _is_cloud_tag(tag):
            continue
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
    return by_tag


def _fetch_model_tags(name: str, *, model_type: str, fallback_params: float | None) -> list[ModelEntry]:
    # The HTML tags page is the authoritative, complete list of tags/sizes.
    # The api/tags endpoint is a small curated subset (often only one tag per
    # model), so use it only to fill in tags the HTML page did not provide.
    by_tag: dict[str, ModelEntry] = {}

    html = _get_html(_model_tags_url(name))
    if html:
        by_tag.update(_parse_tags_from_html(name, html, model_type=model_type, fallback_params=fallback_params))

    for entry in _models_from_api_for_name(name, model_type=model_type):
        if _is_cloud_tag(entry.tag):
            continue
        by_tag.setdefault(entry.tag, entry)

    if by_tag:
        return _limit_tag_entries(list(by_tag.values()))

    # Page loaded but yielded no installable tags (e.g. cloud-only model): skip it.
    if html is not None:
        return []

    # Page failed to load: provide a best-effort fallback only when sized.
    params = fallback_params or 0.0
    size_q4 = estimate_q4_gb(params) if params else 0.0
    if size_q4 <= 0:
        return []
    return [ModelEntry(name=name, tag="latest", params_b=params, size_q4_gb=size_q4, type=model_type)]


def _search_ollama_library_once(keyword: str) -> SearchOutcome:
    """Single attempt to search ollama.com."""
    key = keyword.lower().strip()
    if not key:
        return SearchOutcome(models=[])

    has_more_results = False
    search_page_failed = False
    candidates: list[dict] = []
    parsed, has_more_results, search_page_failed = _fetch_search_pages(keyword)
    if parsed:
        matched = [item for item in parsed if key in item["name"].lower()]
        candidates = matched or parsed

    if not candidates:
        _api_model_sizes()
        candidates, api_has_more = _search_candidates_from_api(keyword)
        has_more_results = api_has_more

    if not candidates:
        api_failed = _api_load_ok is False
        if search_page_failed and (api_failed or _api_load_ok is None):
            return SearchOutcome(models=[], network_error=True)
        return SearchOutcome(models=[])

    to_fetch = candidates[:SEARCH_MODEL_LIMIT]
    _api_model_sizes()  # warm cache before parallel tag requests
    entries: dict[str, ModelEntry] = {}
    workers = _search_tag_workers(len(to_fetch))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _fetch_model_tags,
                item["name"],
                model_type=item["model_type"],
                fallback_params=item["params_b"],
            )
            for item in to_fetch
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
    return SearchOutcome(models=models, has_more_results=has_more_results)


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
