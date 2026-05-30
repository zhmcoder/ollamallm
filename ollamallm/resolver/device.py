"""Resolve any device query string."""

from __future__ import annotations

from ollamallm.models import CpuFamily, HardwareProfile
from ollamallm.resolver.gpu_resolver import is_gpu_query, resolve_gpu
from ollamallm.resolver.mac_resolver import resolve_mac


def resolve_device(text: str, cpu_override: CpuFamily | None = None) -> HardwareProfile:
    stripped = text.strip()
    if is_gpu_query(stripped):
        return resolve_gpu(stripped)
    return resolve_mac(stripped, cpu_override=cpu_override)
