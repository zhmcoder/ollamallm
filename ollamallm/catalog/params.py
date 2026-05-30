"""Parse model names and estimate Q4 memory usage."""

from __future__ import annotations

import re

PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b", re.I)
MOE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b-a(\d+(?:\.\d+)?)\s*b", re.I)
QUANT_SUFFIX_RE = re.compile(r"-(q[248]|fp16)$", re.I)


def split_model_id(model_id: str) -> tuple[str, str]:
    if ":" in model_id:
        name, tag = model_id.split(":", 1)
        return name.lower(), tag.lower()
    return model_id.lower(), "latest"


def parse_params_b(tag: str) -> float | None:
    tag = QUANT_SUFFIX_RE.sub("", tag)
    moe = MOE_RE.search(tag)
    if moe:
        total = float(moe.group(1))
        active = float(moe.group(2))
        # Loaded MoE size is closer to total weights at Q4, not active only.
        return total * 0.45 + active * 0.55
    match = PARAM_RE.search(tag)
    if match:
        return float(match.group(1))
    return None


def estimate_q4_gb(params_b: float, *, model_type: str = "dense") -> float:
    if model_type == "moe":
        return round(params_b * 0.55, 1)
    return round(params_b * 0.55, 1)


def size_gb_from_bytes(size_bytes: int) -> float:
    if size_bytes <= 0:
        return 0.0
    return round(size_bytes / (1024**3), 1)
