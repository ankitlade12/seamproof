"""Command-line interface.

Three subcommands:

* ``seamproof check``   — evaluate seam contracts against a run trace and gate the
  release (non-zero exit when a blocking seam fails). The trace can be a SeamProof
  JSON file (``--trace``) or a UiPath Maestro OpenTelemetry export (``--otel``).
* ``seamproof ingest``  — normalise a Maestro OTLP export into a SeamProof trace.
* ``seamproof publish`` — post the gate result to UiPath Test Manager (or print
  the exact payload with ``--dry-run``).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._version import __version__
from .analyst import analyze
from .contracts import load_contracts
from .errors import SeamProofError
from .gate import evaluate_gate
from .ingest import trace_from_otel
from .publish import PublishConfig, publish
from .report import render
from .trace import Trace

_FORMATS = ("text", "markdown", "json", "junit")


def _add_trace_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-t", "--trace", help="path to a SeamProof run-trace JSON")
    source.add_argument("--otel", help="path to a UiPath Maestro OpenTelemetry (OTLP/JSON) export")
    parser.add_argument(
        "--context", default=None,
        help="path to a JSON context file to merge in when ingesting an --otel export",
    )


def _resolve_trace(args: argparse.Namespace) -> Trace:
    if args.otel:
        return trace_from_otel(args.otel, args.context)
    return Trace.load(args.trace)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seamproof",
        description="The seam tester for agentic processes — assert the handoffs, gate the release.",
    )
    parser.add_argument("--version", action="version", version=f"seamproof {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # -- check --------------------------------------------------------------
    check = sub.add_parser("check", help="evaluate seam contracts against a run trace")
    check.add_argument("-c", "--contracts", required=True, help="contract file or directory")
    _add_trace_source(check)
    check.add_argument("-f", "--format", default="text", choices=_FORMATS, help="report format")
    check.add_argument("-o", "--out", default=None, help="write the report to a file")
    check.add_argument("--no-fail", action="store_true", help="always exit 0, even on NO-GO")
    check.add_argument(
        "--recommend", action="store_true",
        help="run the Seam Analyst agent on failures (root cause + fix); uses the UiPath "
             "LLM Gateway when credentials are present, else a deterministic heuristic",
    )
    check.set_defaults(func=_cmd_check)

    # -- ingest -------------------------------------------------------------
    ingest = sub.add_parser("ingest", help="normalise a Maestro OTLP export into a SeamProof trace")
    ingest.add_argument("--otel", required=True, help="path to the OTLP/JSON export")
    ingest.add_argument("--context", default=None, help="path to a JSON context file to merge in")
    ingest.add_argument("-o", "--out", default=None, help="write the trace JSON to a file (default: stdout)")
    ingest.set_defaults(func=_cmd_ingest)

    # -- publish ------------------------------------------------------------
    pub = sub.add_parser("publish", help="post the gate result to UiPath Test Manager")
    pub.add_argument("-c", "--contracts", required=True, help="contract file or directory")
    _add_trace_source(pub)
    pub.add_argument("--project", default=None, help="Test Manager project id (or UIPATH_PROJECT_ID)")
    pub.add_argument("--base-url", default=None, help="UiPath base URL (or UIPATH_URL)")
    pub.add_argument("--token", default=None, help="access token (or UIPATH_ACCESS_TOKEN / uipath auth)")
    pub.add_argument("--org", default=None, help="organization (or UIPATH_ORGANIZATION_ID)")
    pub.add_argument("--tenant", default=None, help="tenant name (or UIPATH_TENANT_NAME)")
    pub.add_argument("--container", default=None, help="section id to auto-create the seam test cases in")
    pub.add_argument(
        "--testcase-map", default=None,
        help="existing Test Manager test case ids, e.g. 'seam-1=ID1,seam-2=ID2,seam-3=ID3'",
    )
    pub.add_argument("--test-set", default=None, help="name for the Test Manager execution")
    pub.add_argument(
        "--recommend", action="store_true",
        help="attach the Seam Analyst's recommended fix to each failed seam's Test Manager result",
    )
    pub.add_argument("--dry-run", action="store_true", help="print the full request plan without sending")
    pub.set_defaults(func=_cmd_publish)
    return parser


def _cmd_check(args: argparse.Namespace) -> int:
    contracts = load_contracts(args.contracts)
    trace = _resolve_trace(args)
    result = evaluate_gate(trace, contracts)

    recs = analyze(result) if getattr(args, "recommend", False) else None
    report = render(result, args.format, recommendations=recs)
    if args.out:
        Path(args.out).write_text(report + ("" if report.endswith("\n") else "\n"))
        print(render(result, "text", recommendations=recs))
        print(f"\nReport written to {args.out}")
    else:
        print(report)

    return 0 if args.no_fail else result.exit_code


def _cmd_ingest(args: argparse.Namespace) -> int:
    trace = trace_from_otel(args.otel, args.context)
    payload = {
        "trace_id": trace.trace_id,
        "process": trace.process,
        "context": trace.context,
        "events": [
            {
                "id": e.id, "seq": e.seq, "actor": e.actor, "actor_type": e.actor_type,
                "type": e.type, "timestamp": e.timestamp, "attributes": e.attributes,
            }
            for e in trace.events
        ],
    }
    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"Ingested {len(trace.events)} events -> {args.out}")
    else:
        print(text)
    return 0


def _parse_testcase_map(raw: str | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in (raw or "").split(","):
        key, _, value = pair.partition("=")
        if key.strip() and value.strip():
            mapping[key.strip()] = value.strip()
    return mapping


def _cmd_publish(args: argparse.Namespace) -> int:
    contracts = load_contracts(args.contracts)
    trace = _resolve_trace(args)
    result = evaluate_gate(trace, contracts)

    config = PublishConfig.from_env(
        base_url=args.base_url,
        token=args.token,
        organization=args.org,
        tenant=args.tenant,
        project_id=args.project,
        container_id=args.container,
        testcase_ids=_parse_testcase_map(args.testcase_map) or None,
        test_set=args.test_set,
    )
    recs = analyze(result) if getattr(args, "recommend", False) else None
    rec_map = {r.seam_id: r for r in recs} if recs else None
    outcome = publish(result, config, dry_run=args.dry_run, recommendations=rec_map)

    print(render(result, "text", recommendations=recs))
    print()
    if outcome.get("dry_run"):
        print(f"[dry run] {len(outcome['requests'])} requests under {outcome['base']}:")
        print(json.dumps(outcome["requests"], indent=2))
    else:
        print(f"Published to Test Manager — execution {outcome['execution_id']} "
              f"(gate {outcome['decision']})")
        if outcome.get("url"):
            print(outcome["url"])
    return 0


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
