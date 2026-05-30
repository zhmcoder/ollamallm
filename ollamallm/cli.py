"""CLI entry point."""

from __future__ import annotations

import sys

from ollamallm.detector.darwin import detect_local
from ollamallm.matcher.engine import match_models
from ollamallm.models import CpuAmbiguousError, CpuFamily
from ollamallm.output.formatter import HELP_TEXT, format_results
from ollamallm.resolver.device import resolve_device


def main() -> None:
    args = sys.argv[1:]

    if not args:
        _run_local()
        return

    if len(args) == 1 and args[0].lower() in ("help", "-h", "--help"):
        print(HELP_TEXT.rstrip())
        return

    if args[0] == "--json":
        import os

        os.environ["OLLAMALLM_JSON"] = "1"
        args = args[1:]
        if not args:
            _run_local()
            return

    device_text = " ".join(args)
    _run_device(device_text)


def _run_local() -> None:
    try:
        profile = detect_local()
    except RuntimeError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
    recommendations = match_models(profile)
    print(format_results(profile, recommendations, from_local=True))


def _run_device(text: str, cpu_override: CpuFamily | None = None) -> None:
    try:
        profile = resolve_device(text, cpu_override=cpu_override)
    except CpuAmbiguousError as exc:
        if not sys.stdin.isatty():
            print(exc.message(), file=sys.stderr)
            sys.exit(2)
        print(exc.message())
        choice = input("> ").strip().lower()
        if choice in ("1", "apple", "m1"):
            _run_device(text, cpu_override=CpuFamily.APPLE)
            return
        if choice in ("2", "intel"):
            _run_device(text, cpu_override=CpuFamily.INTEL)
            return
        print("请输入 1 或 2", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    recommendations = match_models(profile)
    print(format_results(profile, recommendations, from_local=False))


if __name__ == "__main__":
    main()
