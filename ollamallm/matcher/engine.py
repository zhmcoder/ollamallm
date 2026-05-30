"""Model matching and recommendation engine."""

from __future__ import annotations

from ollamallm.catalog_loader import load_models
from ollamallm.models import (
    CpuFamily,
    HardwareProfile,
    InferenceMode,
    ModelEntry,
    Recommendation,
    Tier,
)


def match_models(profile: HardwareProfile) -> list[Recommendation]:
    models = load_models()
    results: list[Recommendation] = []

    for model in models:
        tier = _tier_for_model(profile, model)
        speed, label = _estimate_speed(profile, model, tier)
        note = None
        if tier == Tier.NO:
            note = "内存不足"
        elif profile.inference_mode == InferenceMode.CPU_ONLY and profile.cpu_family == CpuFamily.INTEL:
            if model.params_b > 8:
                note = "内存/速度均不推荐"
            elif model.params_b > 3 and tier in (Tier.OK, Tier.TIGHT):
                note = "可用但极慢"

        results.append(
            Recommendation(model=model, tier=tier, speed_tok_s=speed, speed_label=label, note=note)
        )

    tier_order = {Tier.BEST: 0, Tier.OK: 1, Tier.TIGHT: 2, Tier.NO: 3}
    results.sort(
        key=lambda r: (
            tier_order[r.tier],
            -r.model.params_b,
            -(r.speed_tok_s or 0),
        )
    )
    return results


def _tier_for_model(profile: HardwareProfile, model: ModelEntry) -> Tier:
    available = profile.available_inference_gb
    size = model.size_q4_gb

    if profile.cpu_family == CpuFamily.INTEL and profile.inference_mode == InferenceMode.CPU_ONLY:
        if model.params_b > 8:
            return Tier.NO
        if model.params_b > 7 and size > available:
            return Tier.NO

    if size > available:
        return Tier.NO
    if size <= available * 0.6:
        if profile.cpu_family == CpuFamily.INTEL and model.params_b > 3:
            return Tier.OK if model.params_b <= 7 else Tier.TIGHT
        return Tier.BEST
    if size <= available * 0.85:
        if profile.cpu_family == CpuFamily.INTEL and model.params_b > 7:
            return Tier.TIGHT
        return Tier.OK
    return Tier.TIGHT


def _estimate_speed(
    profile: HardwareProfile, model: ModelEntry, tier: Tier
) -> tuple[float | None, str]:
    if tier == Tier.NO:
        return None, "—"

    if profile.inference_mode == InferenceMode.CUDA and profile.bandwidth_gbs:
        base = profile.bandwidth_gbs * 0.08
        scale = max(0.15, 1.0 - model.params_b / 80)
        speed = round(base * scale, 0)
        return speed, _speed_label(speed)

    if profile.cpu_family == CpuFamily.INTEL:
        if model.params_b <= 1.5:
            speed = 8.0
        elif model.params_b <= 3:
            speed = 4.0
        elif model.params_b <= 8:
            speed = 1.5
        else:
            speed = 0.5
        return speed, "慢（CPU 推理）"

    bandwidth = profile.bandwidth_gbs or 100
    scale = max(0.2, 1.0 - model.params_b / 100)
    speed = round(bandwidth * 0.35 * scale, 0)
    return speed, _speed_label(speed)


def _speed_label(speed: float) -> str:
    if speed >= 60:
        return "极快"
    if speed >= 30:
        return "流畅"
    if speed >= 15:
        return "可用"
    if speed >= 5:
        return "较慢"
    return "很慢"
