"""macOS local hardware detection."""

from __future__ import annotations

import platform
import re
import subprocess
from typing import Any

from ollamallm.catalog_loader import load_mac_intel_specs, load_mac_model_ids, load_mac_specs
from ollamallm.models import CpuFamily, HardwareProfile, InferenceMode
from ollamallm.profile_builder import build_profile


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _parse_system_profiler() -> dict[str, str]:
    text = _run(["system_profiler", "SPHardwareDataType"])
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _memory_gb_from_fields(fields: dict[str, str]) -> int:
    mem = fields.get("Memory", "")
    match = re.search(r"(\d+)\s*GB", mem, re.I)
    if match:
        return int(match.group(1))
    return 8


def _is_apple_silicon(brand: str) -> bool:
    return brand.startswith("Apple") or "Apple M" in brand


def _lookup_apple_chip(brand: str) -> dict[str, Any] | None:
    specs = load_mac_specs()
    normalized = brand.replace("Apple ", "").strip()
    for spec in specs:
        if spec["chip"].lower() == normalized.lower():
            return spec
    # Partial match: M3 Pro from "Apple M3 Pro"
    for spec in specs:
        if spec["chip"].lower() in normalized.lower() or normalized.lower() in spec["chip"].lower():
            return spec
    return None


def _lookup_intel_by_model_id(model_id: str) -> dict[str, Any] | None:
    for entry in load_mac_model_ids():
        if entry["model_id"] == model_id and entry["cpu_family"] == "intel":
            product = entry["product"]
            for spec in load_mac_intel_specs():
                if spec["product"] in product or product in spec["product"]:
                    return spec
    return None


def detect_local() -> HardwareProfile:
    if platform.system() != "Darwin":
        raise RuntimeError("本机检测目前仅支持 macOS")

    fields = _parse_system_profiler()
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or fields.get("Chip", "")
    model_name = fields.get("Model Name", "Mac")
    model_id = fields.get("Model Identifier", "")
    memory_gb = _memory_gb_from_fields(fields)

    if _is_apple_silicon(brand):
        chip_spec = _lookup_apple_chip(brand)
        bandwidth = chip_spec["bandwidth_gbs"] if chip_spec else 100.0
        chip_label = chip_spec["chip"] if chip_spec else brand.replace("Apple ", "")
        gpu_cores = chip_spec.get("gpu_cores") if chip_spec else None
        chip_display = f"Apple {chip_label}"
        if gpu_cores:
            chip_display += f" ({gpu_cores}-core GPU)"

        return build_profile(
            device_name=model_name,
            cpu_family=CpuFamily.APPLE,
            chip=chip_display,
            memory_gb=memory_gb,
            memory_type="unified",
            bandwidth_gbs=bandwidth,
            inference_mode=InferenceMode.METAL_GPU,
            source="local",
            cpu_confidence="explicit",
            model_id=model_id or None,
        )

    # Intel Mac
    intel_spec = _lookup_intel_by_model_id(model_id) if model_id else None
    gpu = intel_spec["gpu"] if intel_spec else "Intel 集成显卡"
    chip_display = brand or "Intel Core"

    return build_profile(
        device_name=model_name,
        cpu_family=CpuFamily.INTEL,
        chip=chip_display,
        memory_gb=memory_gb,
        memory_type="system",
        bandwidth_gbs=None,
        inference_mode=InferenceMode.CPU_ONLY,
        source="local",
        cpu_confidence="explicit",
        gpu=gpu,
        model_id=model_id or None,
    )
