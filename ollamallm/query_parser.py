"""Parse CLI input into device query vs model keyword search."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ollamallm.resolver.cpu_resolver import APPLE_CHIP_RE, normalize
from ollamallm.resolver.gpu_resolver import is_gpu_query

QueryMode = Literal["local", "device", "search"]

MODEL_FAMILIES = frozenset(
    {
        "qwen",
        "llama",
        "mistral",
        "mixtral",
        "deepseek",
        "gemma",
        "gemma2",
        "gemma3",
        "gemma4",
        "phi",
        "phi3",
        "phi4",
        "codellama",
        "starcoder",
        "starcoder2",
        "yi",
        "solar",
        "command-r",
        "command-r-plus",
        "internlm",
        "internlm2",
        "falcon",
        "vicuna",
        "llava",
        "moondream",
        "minicpm",
        "minicpm-v",
        "granite",
        "granite3",
        "smollm",
        "smollm2",
        "gpt-oss",
        "glm",
        "glm4",
        "ministral",
        "nemotron",
        "devstral",
        "dolphin",
        "openchat",
        "neural-chat",
    }
)

MAC_DEVICE_RE = re.compile(
    r"\b(macbook|mac mini|mac studio|mac pro|imac|macbook air|macbook pro|mba|mbp)\b",
    re.I,
)


@dataclass
class ParsedQuery:
    mode: QueryMode
    keyword: str | None = None
    device_text: str | None = None


def parse_query(text: str) -> ParsedQuery:
    text = text.strip()
    if not text:
        return ParsedQuery(mode="local")

    split = _split_keyword_device(text)
    if split:
        keyword, device = split
        return ParsedQuery(mode="search", keyword=keyword, device_text=device)

    if _looks_like_device(text):
        return ParsedQuery(mode="device", device_text=text)

    first = text.split()[0]
    if _is_model_family(first):
        return ParsedQuery(mode="search", keyword=text)

    return ParsedQuery(mode="search", keyword=text)


def _split_keyword_device(text: str) -> tuple[str, str] | None:
    words = text.split()
    if len(words) < 2:
        return None
    if not _is_model_family(words[0]):
        return None

    device_text = " ".join(words[1:])
    if _looks_like_device(device_text):
        return words[0], device_text
    return None


def _is_model_family(word: str) -> bool:
    w = word.lower()
    if w in MODEL_FAMILIES:
        return True
    return any(w.startswith(f"{family}") or family.startswith(w) for family in MODEL_FAMILIES if len(w) >= 2)


def _looks_like_device(text: str) -> bool:
    t = normalize(text)
    if is_gpu_query(t):
        return True
    if MAC_DEVICE_RE.search(t):
        return True
    if re.search(r"\b(intel|core i[3579]|xeon)\b", t):
        return True
    if re.search(r"\b(20\d{2})\b", t) and ("mac" in t or "imac" in t or "macbook" in t):
        return True

    words = t.split()
    if len(words) == 1 and APPLE_CHIP_RE.search(words[0]):
        return True

    if APPLE_CHIP_RE.search(t):
        if re.search(r"\b\d+\s*g(?:b)?\b", t):
            return True
        if re.search(r"\b(pro|max|ultra)\b", t):
            return True
        if MAC_DEVICE_RE.search(t):
            return True

    return False
