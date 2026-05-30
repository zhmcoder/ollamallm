"""Mac CPU architecture resolution."""

from __future__ import annotations

import re
from typing import Literal

from ollamallm.catalog_loader import load_mac_model_ids
from ollamallm.models import CpuFamily

# product line -> (intel_last_year, apple_first_year, ambiguous_years)
PRODUCT_TIMELINE: dict[str, tuple[int | None, int | None, list[int]]] = {
    "macbook air": (2019, 2020, [2020]),
    "macbook pro 13": (2020, 2020, [2020]),
    "macbook pro": (2019, 2021, [2020]),
    "mac mini": (2018, 2020, [2020]),
    "imac 27": (2020, None, []),
    "imac": (2020, 2021, []),
    "mac studio": (None, 2022, []),
    "mac pro": (2019, 2023, []),
}

APPLE_CHIP_RE = re.compile(
    r"\b(m[1-4](?:\s*(?:pro|max|ultra))?)\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
MEMORY_RE = re.compile(r"\b(\d+)\s*g(?:b)?\b", re.I)
MODEL_ID_RE = re.compile(r"\b(Mac(?:Book|mini|Pro|BookPro|BookAir)[A-Za-z0-9,]+)\b")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def detect_cpu_from_text(text: str) -> tuple[CpuFamily | None, Literal["explicit", "inferred"] | None]:
    t = normalize(text)
    if re.search(r"\b(intel|core i[3579]|xeon)\b", t):
        return CpuFamily.INTEL, "explicit"
    if re.search(r"\b(apple\s*silicon|apple\s*chip)\b", t):
        return CpuFamily.APPLE, "explicit"
    if APPLE_CHIP_RE.search(t):
        return CpuFamily.APPLE, "explicit"

    model_id_match = MODEL_ID_RE.search(text)
    if model_id_match:
        mid = model_id_match.group(1)
        for entry in load_mac_model_ids():
            if entry["model_id"].lower() == mid.lower():
                fam = CpuFamily.APPLE if entry["cpu_family"] == "apple" else CpuFamily.INTEL
                return fam, "inferred"

    year_match = YEAR_RE.search(t)
    product = _detect_product_line(t)
    if product and year_match:
        year = int(year_match.group(1))
        intel_last, apple_first, ambiguous = PRODUCT_TIMELINE.get(product, (None, None, []))
        if year in ambiguous:
            return None, None
        if intel_last is not None and year <= intel_last and (apple_first is None or year < apple_first):
            return CpuFamily.INTEL, "inferred"
        if apple_first is not None and year >= apple_first:
            return CpuFamily.APPLE, "inferred"
        if product == "macbook pro" and year >= 2021:
            return CpuFamily.APPLE, "inferred"
        if product == "macbook pro" and year <= 2019:
            return CpuFamily.INTEL, "inferred"

    if product and not year_match:
        return None, None

    return None, None


def is_cpu_ambiguous(text: str) -> bool:
    cpu, _ = detect_cpu_from_text(text)
    if cpu is not None:
        return False
    t = normalize(text)
    if APPLE_CHIP_RE.search(t) or re.search(r"\b(intel|rtx|geforce|rx)\b", t):
        return False
    product = _detect_product_line(t)
    year_match = YEAR_RE.search(t)
    if product and year_match:
        year = int(year_match.group(1))
        _, _, ambiguous = PRODUCT_TIMELINE.get(product, (None, None, []))
        return year in ambiguous
    if product and not year_match:
        return True
    return False


def _detect_product_line(text: str) -> str | None:
    if "macbook air" in text or re.search(r"\bmba\b", text):
        return "macbook air"
    if "macbook pro" in text or re.search(r"\bmbp\b", text):
        if re.search(r"\b13\b", text):
            return "macbook pro 13"
        return "macbook pro"
    if "mac mini" in text:
        return "mac mini"
    if "imac 27" in text or ("imac" in text and "27" in text):
        return "imac 27"
    if "imac" in text:
        return "imac"
    if "mac studio" in text:
        return "mac studio"
    if "mac pro" in text:
        return "mac pro"
    return None


def extract_memory_gb(text: str) -> int | None:
    match = MEMORY_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_apple_chip(text: str) -> str | None:
    match = APPLE_CHIP_RE.search(text)
    if not match:
        return None
    raw = match.group(1).upper().replace("  ", " ")
    parts = raw.split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {' '.join(p.capitalize() for p in parts[1:])}"


def extract_year(text: str) -> int | None:
    match = YEAR_RE.search(text)
    return int(match.group(1)) if match else None
