"""Resolve GPU device strings to hardware profiles."""

from __future__ import annotations

import re

from ollamallm.catalog_loader import load_gpu_specs
from ollamallm.profile_builder import build_profile
from ollamallm.models import CpuFamily, HardwareProfile, InferenceMode
from ollamallm.resolver.cpu_resolver import extract_memory_gb, normalize


def is_gpu_query(text: str) -> bool:
    t = normalize(text)
    return bool(re.search(r"\b(rtx|gtx|rx|geforce|radeon)\b", t)) or bool(
        re.search(r"\b(4090|4080|4070|4060|3090|3080|3060|5090|5070)\b", t)
    )


def resolve_gpu(text: str) -> HardwareProfile:
    t = normalize(text)
    vram_override = extract_memory_gb(text)

    for spec in load_gpu_specs():
        names = [spec["name"].lower()] + [a.lower() for a in spec.get("aliases", [])]
        if not any(n in t for n in names):
            continue

        vram = spec["vram_gb"]
        if spec.get("variants") and vram_override:
            for variant in spec["variants"]:
                if variant["vram_gb"] == vram_override:
                    vram = variant["vram_gb"]
                    break
        elif vram_override:
            vram = vram_override

        return build_profile(
            device_name=f"NVIDIA {spec['name']}",
            cpu_family=CpuFamily.APPLE,  # unused for CUDA matching
            chip=spec["name"],
            memory_gb=vram,
            memory_type="vram",
            bandwidth_gbs=spec.get("bandwidth_gbs"),
            inference_mode=InferenceMode.CUDA,
            source="catalog",
            cpu_confidence="explicit",
            gpu=f"{vram} GB VRAM",
        )

    raise ValueError(
        f"无法识别显卡型号「{text.strip()}」\n\n"
        "示例:\n"
        "  ollamallm RTX 4090\n"
        "  ollamallm RTX 3060 12GB"
    )
