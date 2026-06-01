"""CLI entry point."""

from __future__ import annotations

import sys

from ollamallm.detector.darwin import detect_local
from ollamallm.catalog.online import search_ollama_library
from ollamallm.matcher.engine import match_models
from ollamallm.models import CpuAmbiguousError, CpuFamily, HardwareProfile
from ollamallm.output.formatter import (
    HELP_TEXT,
    format_no_search_results,
    format_results,
    format_search_network_error,
)
from ollamallm.output.terminal_io import configure_terminal_output, terminal_print
from ollamallm.query_parser import ParsedQuery, parse_query
from ollamallm.resolver.device import resolve_device


def main() -> None:
    configure_terminal_output()
    args = sys.argv[1:]

    if not args:
        _run_local()
        return

    if len(args) == 1 and args[0].lower() in ("help", "-h", "--help"):
        terminal_print(HELP_TEXT.rstrip())
        return

    if args[0] == "--json":
        import os

        os.environ["OLLAMALLM_JSON"] = "1"
        args = args[1:]
        if not args:
            _run_local()
            return

    query = parse_query(" ".join(args))
    if query.mode == "local":
        _run_local()
    elif query.mode == "device":
        _run_device(query.device_text or "")
    elif query.mode == "search":
        _run_search(query.keyword or "", query.device_text)


def _run_local() -> None:
    try:
        profile = detect_local()
    except RuntimeError as exc:
        terminal_print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
    recommendations = match_models(profile)
    terminal_print(format_results(profile, recommendations, from_local=True))


def _run_search(keyword: str, device_text: str | None) -> None:
    if device_text:
        try:
            profile = _resolve_device(device_text)
        except SystemExit:
            return
        from_local = False
    else:
        try:
            profile = detect_local()
        except RuntimeError as exc:
            terminal_print(f"错误: {exc}", file=sys.stderr)
            sys.exit(1)
        from_local = True

    outcome = search_ollama_library(keyword)
    if outcome.network_error:
        terminal_print(format_search_network_error(keyword))
        sys.exit(1)
    if not outcome.models:
        terminal_print(format_no_search_results(keyword))
        sys.exit(1)
    recommendations = match_models(profile, outcome.models)
    terminal_print(
        format_results(
            profile,
            recommendations,
            from_local=from_local,
            search_keyword=keyword,
            search_has_more=outcome.has_more_results,
        )
    )


def _run_device(text: str, cpu_override: CpuFamily | None = None) -> None:
    try:
        profile = _resolve_device(text, cpu_override=cpu_override)
    except SystemExit:
        return
    recommendations = match_models(profile)
    terminal_print(format_results(profile, recommendations, from_local=False))


def _resolve_device(text: str, cpu_override: CpuFamily | None = None) -> HardwareProfile:
    try:
        return resolve_device(text, cpu_override=cpu_override)
    except CpuAmbiguousError as exc:
        if not sys.stdin.isatty():
            terminal_print(exc.message(), file=sys.stderr)
            sys.exit(2)
        terminal_print(exc.message())
        choice = input("> ").strip().lower()
        if choice in ("1", "apple", "m1"):
            return _resolve_device(text, cpu_override=CpuFamily.APPLE)
        if choice in ("2", "intel"):
            return _resolve_device(text, cpu_override=CpuFamily.INTEL)
        terminal_print("请输入 1 或 2", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        terminal_print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
