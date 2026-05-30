"""Build HardwareProfile with standard memory budget."""

from __future__ import annotations

from ollamallm.models import CpuFamily, HardwareProfile, InferenceMode


def build_profile(
    *,
    device_name: str,
    cpu_family: CpuFamily,
    chip: str,
    memory_gb: int,
    memory_type: str,
    bandwidth_gbs: float | None,
    inference_mode: InferenceMode,
    source: str,
    cpu_confidence: str,
    gpu: str | None = None,
    cpu_inference_note: str | None = None,
    model_id: str | None = None,
) -> HardwareProfile:
    if memory_type == "vram":
        reserved, kv_cache, runtime = 2.0, 2.0, 0.5
    elif cpu_family == CpuFamily.APPLE:
        reserved, kv_cache, runtime = 4.0, 2.0, 0.5
    else:
        reserved, kv_cache, runtime = 2.0, 2.0, 0.5

    available = max(0.5, memory_gb - reserved - kv_cache - runtime)

    return HardwareProfile(
        device_name=device_name,
        cpu_family=cpu_family,
        chip=chip,
        memory_gb=memory_gb,
        memory_type=memory_type,  # type: ignore[arg-type]
        available_inference_gb=round(available, 1),
        bandwidth_gbs=bandwidth_gbs,
        inference_mode=inference_mode,
        source=source,  # type: ignore[arg-type]
        cpu_confidence=cpu_confidence,  # type: ignore[arg-type]
        gpu=gpu,
        cpu_inference_note=cpu_inference_note,
        model_id=model_id,
    )
