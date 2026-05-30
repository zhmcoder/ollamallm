"""Resolve Mac device strings to hardware profiles."""

from __future__ import annotations

import re

from ollamallm.catalog_loader import load_mac_intel_specs, load_mac_model_ids, load_mac_specs
from ollamallm.profile_builder import build_profile
from ollamallm.models import CpuAmbiguousError, CpuFamily, HardwareProfile, InferenceMode
from ollamallm.resolver.cpu_resolver import (
    detect_cpu_from_text,
    extract_apple_chip,
    extract_memory_gb,
    extract_year,
    is_cpu_ambiguous,
    normalize,
)

INTEL_PRODUCT_MAP = {
    "macbook pro 2019": "MacBook Pro 16 2019",
    "macbook pro 15 2019": "MacBook Pro 15 2019",
    "macbook pro 16 2019": "MacBook Pro 16 2019",
    "macbook air 2018": "MacBook Air 2018",
    "macbook air 2019": "MacBook Air 2019",
    "mac mini 2018": "Mac mini 2018",
    "imac 27 2020": "iMac 27 2020",
    "imac 2020": "iMac 27 2020",
}


def resolve_mac(text: str, cpu_override: CpuFamily | None = None) -> HardwareProfile:
    if is_cpu_ambiguous(text) and cpu_override is None:
        raise CpuAmbiguousError(
            input_text=text,
            candidates=[
                (1, CpuFamily.APPLE, "Apple 芯片 (M1)"),
                (2, CpuFamily.INTEL, "Intel 芯片"),
            ],
        )

    cpu_family = cpu_override
    cpu_confidence = "user_selected" if cpu_override else None
    cpu_note = None

    if cpu_family is None:
        detected, conf = detect_cpu_from_text(text)
        cpu_family = detected or CpuFamily.APPLE
        cpu_confidence = conf or "inferred"
        if conf == "inferred":
            cpu_note = f"根据「{text.strip()}」自动判定；若不对，请在型号中加 Intel 或 M1 重试"

    if cpu_family == CpuFamily.APPLE:
        return _resolve_apple(text, cpu_confidence or "inferred", cpu_note)
    return _resolve_intel(text, cpu_confidence or "inferred", cpu_note)


def _resolve_apple(text: str, confidence: str, note: str | None) -> HardwareProfile:
    chip_name = extract_apple_chip(text)
    memory_gb = extract_memory_gb(text)

    if chip_name:
        spec = _find_apple_spec(chip_name)
        if spec:
            mem = memory_gb or _pick_memory(spec, memory_gb)
            device = _device_label(text, chip_name)
            chip_display = f"Apple {spec['chip']} ({spec['gpu_cores']}-core GPU)"
            return build_profile(
                device_name=device,
                cpu_family=CpuFamily.APPLE,
                chip=chip_display,
                memory_gb=mem,
                memory_type="unified",
                bandwidth_gbs=spec["bandwidth_gbs"],
                inference_mode=InferenceMode.METAL_GPU,
                source="catalog",
                cpu_confidence=confidence,  # type: ignore[arg-type]
                cpu_inference_note=note,
            )

    # Infer from product line + year
    year = extract_year(text)
    t = normalize(text)
    if "macbook pro" in t and year and year >= 2021:
        chip_name = chip_name or "M1 Pro"
    elif "mac studio" in t:
        chip_name = chip_name or "M2 Max"
    elif "mac mini" in t and (year is None or year >= 2020):
        chip_name = chip_name or "M1"
    else:
        chip_name = chip_name or "M1"

    spec = _find_apple_spec(chip_name) or load_mac_specs()[0]
    mem = memory_gb or spec["default_memory_gb"]
    device = _device_label(text, spec["chip"])
    chip_display = f"Apple {spec['chip']} ({spec['gpu_cores']}-core GPU)"

    return build_profile(
        device_name=device,
        cpu_family=CpuFamily.APPLE,
        chip=chip_display,
        memory_gb=mem,
        memory_type="unified",
        bandwidth_gbs=spec["bandwidth_gbs"],
        inference_mode=InferenceMode.METAL_GPU,
        source="catalog",
        cpu_confidence=confidence,  # type: ignore[arg-type]
        cpu_inference_note=note,
    )


def _resolve_intel(text: str, confidence: str, note: str | None) -> HardwareProfile:
    memory_gb = extract_memory_gb(text)
    t = normalize(text)
    product_key = _intel_product_key(t)
    spec = None
    for key, product in INTEL_PRODUCT_MAP.items():
        if key in product_key or product_key in key:
            spec = next((s for s in load_mac_intel_specs() if s["product"] == product), None)
            if spec:
                break

    if spec is None:
        year = extract_year(text)
        if "macbook pro" in t:
            spec = next(s for s in load_mac_intel_specs() if "MacBook Pro 16 2019" in s["product"])
        elif "macbook air" in t:
            spec = next(s for s in load_mac_intel_specs() if "2019" in s["product"])
        elif "mac mini" in t:
            spec = next(s for s in load_mac_intel_specs() if "mini 2018" in s["product"])
        elif "imac" in t:
            spec = next(s for s in load_mac_intel_specs() if "iMac 27" in s["product"])
        else:
            spec = load_mac_intel_specs()[0]
        if note is None and year:
            note = f"根据「{text.strip()}」自动判定；若不对，请在型号中加 Intel 或 M1 重试"

    mem = memory_gb or spec["default_memory_gb"]
    device = spec["product"]
    if memory_gb:
        device = f"{spec['product']} ({memory_gb}GB)"

    return build_profile(
        device_name=device,
        cpu_family=CpuFamily.INTEL,
        chip=spec["chip"],
        memory_gb=mem,
        memory_type="system",
        bandwidth_gbs=None,
        inference_mode=InferenceMode.CPU_ONLY,
        source="catalog",
        cpu_confidence=confidence,  # type: ignore[arg-type]
        gpu=spec.get("gpu"),
        cpu_inference_note=note,
    )


def _find_apple_spec(chip_name: str) -> dict | None:
    normalized = chip_name.upper().replace("  ", " ")
    for spec in load_mac_specs():
        if spec["chip"].upper() == normalized:
            return spec
    # M2 matches before M2 Pro — sort by length desc
    for spec in sorted(load_mac_specs(), key=lambda s: len(s["chip"]), reverse=True):
        if spec["chip"].upper() in normalized or normalized in spec["chip"].upper():
            return spec
    return None


def _pick_memory(spec: dict, requested: int | None) -> int:
    if requested and requested in spec["memory_gb"]:
        return requested
    if requested:
        return requested
    return spec["default_memory_gb"]


def _device_label(text: str, chip: str) -> str:
    t = normalize(text)
    if "macbook air" in t:
        return f"MacBook Air ({chip})"
    if "macbook pro" in t:
        return f"MacBook Pro ({chip})"
    if "mac mini" in t:
        return f"Mac mini ({chip})"
    if "mac studio" in t:
        return f"Mac Studio ({chip})"
    if "imac" in t:
        return f"iMac ({chip})"
    return f"Mac ({chip})"


def _intel_product_key(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip())
