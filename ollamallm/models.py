"""Core data types for ollamallm."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class CpuFamily(str, Enum):
    APPLE = "apple"
    INTEL = "intel"


class InferenceMode(str, Enum):
    METAL_GPU = "metal_gpu"
    CPU_ONLY = "cpu_only"
    CUDA = "cuda"


class Tier(str, Enum):
    BEST = "best"
    OK = "ok"
    TIGHT = "tight"
    NO = "no"


@dataclass
class HardwareProfile:
    device_name: str
    cpu_family: CpuFamily
    chip: str
    memory_gb: int
    memory_type: Literal["unified", "system", "vram"]
    available_inference_gb: float
    source: Literal["local", "catalog"] = "catalog"
    cpu_confidence: Literal["explicit", "inferred", "user_selected"] = "inferred"
    cpu_inference_note: str | None = None
    gpu: str | None = None
    bandwidth_gbs: float | None = None
    inference_mode: InferenceMode = InferenceMode.METAL_GPU
    model_id: str | None = None


@dataclass
class ModelEntry:
    name: str
    tag: str
    params_b: float
    size_q4_gb: float
    type: str = "dense"

    @property
    def full_name(self) -> str:
        return f"{self.name}:{self.tag}"


@dataclass
class Recommendation:
    model: ModelEntry
    tier: Tier
    speed_tok_s: float | None
    speed_label: str
    note: str | None = None


@dataclass
class CpuAmbiguousError:
    """Raised when CPU family cannot be determined."""

    input_text: str
    candidates: list[tuple[int, CpuFamily, str]] = field(default_factory=list)

    def message(self) -> str:
        lines = [
            "",
            "无法唯一确定 CPU，请选一项：",
            "  1  Apple 芯片 (M1)",
            "  2  Intel 芯片",
            "",
            "也可一次说清，例如：",
            f"  ollamallm {self.input_text} Intel",
            f"  ollamallm {self.input_text} M1",
            "",
        ]
        return "\n".join(lines)


TIER_ICONS = {
    Tier.BEST: "⭐",
    Tier.OK: "✅",
    Tier.TIGHT: "⚠️",
    Tier.NO: "❌",
}
