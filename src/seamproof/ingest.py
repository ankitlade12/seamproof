"""Ingest a UiPath Maestro run as a SeamProof trace.

Maestro emits agent traces over **OpenTelemetry** (OTLP/JSON). This adapter
normalises an OTLP trace export into the platform-neutral SeamProof trace shape
so the gate can evaluate a real run. It is the bridge between "the engine runs on
fixtures" and "the engine runs on UiPath" — and, because OTLP is a documented
standard, it can be built and tested offline against the spec.

Mapping
-------
* each OTLP **span** becomes a trace **event** (`span.name` -> event `type`);
* `actor` / `actor_type` are read from span attributes (inferred from the span
  name when absent);
* a span named ``run.context`` carries the static business context (PO, vendor
  master, ceilings, SLOs) and is lifted into the trace `context` rather than
  kept as an event;
* an external context file may be supplied to override or supply that context.

OTLP attribute values are typed (`stringValue`, `intValue`, `doubleValue`,
`boolValue`, `arrayValue`, `kvlistValue`); they are decoded recursively, so
nested business context survives the round trip.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import TraceError
from .trace import Trace

_ACTOR_KEYS = ("actor", "actor.name")
_ACTOR_TYPE_KEYS = ("actor_type", "actor.type")
_CONTEXT_SPAN_NAMES = ("run.context", "process.context")


def _otel_value(value: dict[str, Any]) -> Any:
    """Decode a single OTLP ``AnyValue`` into a plain Python value."""
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "arrayValue" in value:
        return [_otel_value(v) for v in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return {kv["key"]: _otel_value(kv["value"]) for kv in value["kvlistValue"].get("values", [])}
    return None


def _attributes(attributes: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {a["key"]: _otel_value(a["value"]) for a in attributes or []}


def _iso(nanos: Any) -> str | None:
    if nanos is None:
        return None
    try:
        seconds = int(nanos) / 1e9
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _infer_actor_type(span_name: str) -> str:
    prefix = span_name.split(".", 1)[0]
    return {
        "agent": "agent",
        "robot": "robot",
        "human": "human",
        "routing": "router",
        "route": "router",
        "run": "system",
        "process": "system",
    }.get(prefix, "system")


def _collect_spans(otel: dict[str, Any]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for resource_span in otel.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", resource_span.get("instrumentationLibrarySpans", [])):
            spans.extend(scope_span.get("spans", []))
    return spans


def _resource_process(otel: dict[str, Any]) -> str | None:
    for resource_span in otel.get("resourceSpans", []):
        attrs = _attributes(resource_span.get("resource", {}).get("attributes"))
        for key in ("process", "process.name", "service.name"):
            if key in attrs:
                return str(attrs[key])
    return None


def otel_to_trace(otel: dict[str, Any], context: dict[str, Any] | None = None) -> Trace:
    """Convert a parsed OTLP trace document into a :class:`Trace`."""
    spans = _collect_spans(otel)
    if not spans:
        raise TraceError("OTLP document contains no spans")

    spans = sorted(spans, key=lambda s: int(s.get("startTimeUnixNano", 0)))

    span_context: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    seq = 0
    trace_id = None
    for span in spans:
        attrs = _attributes(span.get("attributes"))
        name = span.get("name", "event")
        if name in _CONTEXT_SPAN_NAMES:
            span_context.update(attrs)
            continue
        if trace_id is None:
            trace_id = span.get("traceId")
        seq += 1
        actor = next((attrs[k] for k in _ACTOR_KEYS if k in attrs), "unknown")
        actor_type = next((attrs[k] for k in _ACTOR_TYPE_KEYS if k in attrs), _infer_actor_type(name))
        payload = {k: v for k, v in attrs.items() if k not in _ACTOR_KEYS and k not in _ACTOR_TYPE_KEYS}
        events.append(
            {
                "id": span.get("spanId", f"span-{seq}"),
                "seq": seq,
                "actor": actor,
                "actor_type": actor_type,
                "type": name,
                "timestamp": _iso(span.get("startTimeUnixNano")),
                "attributes": payload,
            }
        )

    merged_context = {**span_context, **(context or {})}
    return Trace.from_dict(
        {
            "trace_id": trace_id or "otel-unknown",
            "process": _resource_process(otel) or "unknown",
            "context": merged_context,
            "events": events,
        }
    )


def load_otel(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        return json.loads(p.read_text())
    except FileNotFoundError as exc:
        raise TraceError(f"OTLP file not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise TraceError(f"OTLP file {p} is not valid JSON: {exc}") from exc


def load_context(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text())
    except FileNotFoundError as exc:
        raise TraceError(f"context file not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise TraceError(f"context file {p} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TraceError(f"context file {p} must be a JSON object")
    return data


def trace_from_otel(otel_path: str | Path, context_path: str | Path | None = None) -> Trace:
    """Load an OTLP export (and optional context file) into a :class:`Trace`."""
    context = load_context(context_path) if context_path else None
    return otel_to_trace(load_otel(otel_path), context)
