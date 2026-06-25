"""Command-line interface.

``seamproof check`` is the gate: point it at a directory of seam contracts and a
run trace, and it prints the PASS/FAIL report and exits non-zero when a blocking
seam fails. That non-zero exit is what wires the gate into CI or a UiPath Test
pipeline — a failing seam stops the release.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .contracts import load_contracts
from .errors import SeamProofError
from .gate import evaluate_gate
from .report import render
from .trace import Trace

_FORMATS = ("text", "markdown", "json", "junit")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seamproof",
        description="The seam tester for agentic processes — assert the handoffs, gate the release.",
    )
    parser.add_argument("--version", action="version", version=f"seamproof {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="evaluate seam contracts against a run trace")
    check.add_argument(
        "-c", "--contracts", required=True,
        help="path to a contract file or a directory of contracts",
    )
    check.add_argument(
        "-t", "--trace", required=True,
        help="path to the run-trace JSON to evaluate",
    )
    check.add_argument(
        "-f", "--format", default="text", choices=_FORMATS,
        help="report format (default: text)",
    )
    check.add_argument(
        "-o", "--out", default=None,
        help="write the report to a file instead of stdout",
    )
    check.add_argument(
        "--no-fail", action="store_true",
        help="always exit 0, even on a NO-GO gate (report only)",
    )
    check.set_defaults(func=_cmd_check)
    return parser


def _cmd_check(args: argparse.Namespace) -> int:
    contracts = load_contracts(args.contracts)
    trace = Trace.load(args.trace)
    result = evaluate_gate(trace, contracts)

    report = render(result, args.format)
    if args.out:
        Path(args.out).write_text(report + ("\n" if not report.endswith("\n") else ""))
        # Even when writing a machine format to a file, give the console a verdict.
        print(render(result, "text"))
        print(f"\nReport written to {args.out}")
    else:
        print(report)

    if args.no_fail:
        return 0
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SeamProofError as exc:
        print(f"seamproof: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
