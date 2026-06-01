"""Terminal output helpers for UTF-8 and icon compatibility."""

from __future__ import annotations

import os
import sys
from typing import TextIO

from ollamallm.models import Tier

TIER_ICONS_EMOJI = {
    Tier.BEST: "⭐",
    Tier.OK: "✅",
    Tier.TIGHT: "⚠️",
    Tier.NO: "❌",
}

TIER_ICONS_SYMBOL = {
    Tier.BEST: "★",
    Tier.OK: "✔",
    Tier.TIGHT: "⚠",
    Tier.NO: "✘",
}


def configure_terminal_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _icon_mode() -> str:
    mode = os.environ.get("OLLAMALLM_ICONS", "").strip().lower()
    if mode in ("emoji", "symbol"):
        return mode
    term = (os.environ.get("TERM_PROGRAM") or "").lower()
    if term in ("vscode", "cursor"):
        return "symbol"
    encoding = (getattr(sys.stdout, "encoding", None) or "utf-8").lower().replace("-", "")
    if encoding != "utf8":
        return "symbol"
    return "emoji"


def tier_icon(tier: Tier) -> str:
    if _icon_mode() == "symbol":
        return TIER_ICONS_SYMBOL[tier]
    return TIER_ICONS_EMOJI[tier]


def tier_icons() -> dict[Tier, str]:
    icons = TIER_ICONS_SYMBOL if _icon_mode() == "symbol" else TIER_ICONS_EMOJI
    return dict(icons)


def inline_warning_icon() -> str:
    return "⚠" if _icon_mode() == "symbol" else "⚠️"


def terminal_print(text: str = "", *, file: TextIO | None = None, end: str = "\n") -> None:
    stream = file or sys.stdout
    configure_terminal_output()
    payload = text if not end or text.endswith(end) else text + end
    data = payload.encode("utf-8", errors="replace")
    if hasattr(stream, "buffer"):
        stream.buffer.write(data)
        stream.buffer.flush()
        return
    stream.write(payload)
    stream.flush()
