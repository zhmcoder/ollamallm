"""Terminal output formatting."""

from __future__ import annotations

import json
import os

from ollamallm.models import (
    CpuFamily,
    HardwareProfile,
    Recommendation,
    TIER_ICONS,
    Tier,
)


def format_results(
    profile: HardwareProfile,
    recommendations: list[Recommendation],
    *,
    from_local: bool,
) -> str:
    if os.environ.get("OLLAMALLM_JSON"):
        return _format_json(profile, recommendations)

    runnable = [r for r in recommendations if r.tier != Tier.NO]
    not_runnable = [r for r in recommendations if r.tier == Tier.NO]
    total_runnable = len(runnable)
    total_no = len(not_runnable)
    recommendations = runnable + not_runnable[:8]

    lines: list[str] = []
    header = "检测到本机配置" if from_local else "设备规格（来自型号库）"
    lines.append(header)
    lines.append("─" * 38)
    lines.append(f"设备    : {profile.device_name}")
    if profile.memory_type == "vram":
        lines.append("类型    : NVIDIA GPU (CUDA)")
    else:
        lines.append(f"CPU 架构: {_cpu_label(profile)}")
    lines.append(f"芯片    : {profile.chip}")

    if profile.memory_type == "unified":
        lines.append(f"内存    : {profile.memory_gb} GB 统一内存")
    elif profile.memory_type == "vram":
        lines.append(f"显存    : {profile.memory_gb} GB")
    else:
        lines.append(f"内存    : {profile.memory_gb} GB")

    if profile.gpu and profile.cpu_family == CpuFamily.INTEL:
        lines.append(f"GPU     : {profile.gpu}")

    if profile.bandwidth_gbs and profile.memory_type != "vram":
        lines.append(f"带宽    : {profile.bandwidth_gbs:.0f} GB/s")

    avail_note = "已扣除系统与 KV 预留"
    if profile.inference_mode.value == "cpu_only" and profile.cpu_family == CpuFamily.INTEL:
        avail_note = "CPU 推理为主，速度显著低于 Apple Silicon"
    elif profile.memory_type == "vram":
        avail_note = "已扣除驱动与 KV 预留"
    lines.append(f"可用推理: ~{profile.available_inference_gb} GB（{avail_note}）")

    if profile.inference_mode.value == "cpu_only" and profile.cpu_family == CpuFamily.INTEL:
        lines.append("")
        lines.append("⚠️  Intel Mac 说明: Ollama 主要使用 CPU 推理，大模型速度较慢，建议 7B 以下模型")

    lines.append("")
    lines.append("推荐 Ollama 模型")
    lines.append("─" * 38)

    shown_no = 0
    for rec in recommendations:
        if rec.tier == Tier.NO:
            shown_no += 1

        icon = TIER_ICONS[rec.tier]
        name = rec.model.full_name.ljust(20)
        size = f"~{rec.model.size_q4_gb:.1f} GB".ljust(9)
        if rec.speed_tok_s is not None:
            speed = f"~{rec.speed_tok_s:.0f} tok/s".ljust(11)
        else:
            speed = "—".ljust(11)

        pull = f"ollama pull {rec.model.full_name}"
        if rec.tier == Tier.NO:
            detail = rec.note or "内存不足"
            lines.append(f"{icon} {name} {size} {speed} {detail}")
        elif rec.note and rec.tier in (Tier.TIGHT, Tier.OK):
            lines.append(f"{icon} {name} {size} {speed} {rec.note}")
        else:
            lines.append(f"{icon} {name} {size} {speed} {pull}")

    lines.append("")
    runnable_count = total_runnable
    no_shown = min(8, total_no)
    summary = f"共 {runnable_count} 个可安装模型"
    if total_no:
        summary += f"（另有 {total_no} 个内存不足" + (f"，展示前 {no_shown} 个" if total_no > no_shown else "") + "）"
    lines.append(summary)
    lines.append("提示: 复制 ollama pull 命令即可安装")
    return "\n".join(lines)


def _cpu_label(profile: HardwareProfile) -> str:
    label = "Apple Silicon" if profile.cpu_family == CpuFamily.APPLE else "Intel"
    if profile.cpu_inference_note:
        return f"{label}（{profile.cpu_inference_note}）"
    return label


def _format_json(profile: HardwareProfile, recommendations: list[Recommendation]) -> str:
    data = {
        "hardware": {
            "source": profile.source,
            "device": profile.device_name,
            "cpu_family": profile.cpu_family.value,
            "cpu_family_label": "Apple Silicon" if profile.cpu_family == CpuFamily.APPLE else "Intel",
            "cpu_confidence": profile.cpu_confidence,
            "cpu_inference_note": profile.cpu_inference_note,
            "chip": profile.chip,
            "memory_gb": profile.memory_gb,
            "memory_type": profile.memory_type,
            "gpu": profile.gpu,
            "bandwidth_gbs": profile.bandwidth_gbs,
            "available_inference_gb": profile.available_inference_gb,
        },
        "recommendations": [
            {
                "model": r.model.full_name,
                "size_gb": r.model.size_q4_gb,
                "quant": "q4_K_M",
                "tier": r.tier.value,
                "speed_tok_s": r.speed_tok_s,
                "speed_label": r.speed_label,
                "pull_command": f"ollama pull {r.model.full_name}",
                "note": r.note,
            }
            for r in recommendations
            if r.tier != Tier.NO or recommendations.index(r) < len(recommendations)
        ],
    }
    # JSON: all runnable models
    data["recommendations"] = [
        item for item in data["recommendations"] if item["tier"] != "no"
    ]
    return json.dumps(data, ensure_ascii=False, indent=2)


HELP_TEXT = """\
ollamallm — 根据硬件推荐可安装的 Ollama 模型

用法:
  ollamallm                  查本机
  ollamallm <型号>           查指定设备

示例:
  ollamallm
  ollamallm M2 Pro 16GB
  ollamallm MacBook Air M1 8GB
  ollamallm MacBook Pro 2019
  ollamallm MacBook Pro 2020 Intel
  ollamallm RTX 4090

型号里加上 Intel 或 M1 可指定 CPU 类型。
"""
