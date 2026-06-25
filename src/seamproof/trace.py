"""Run-trace model.

A *trace* is the ordered record of what happened during one execution of the
system under test: the agent's output, the routing decision, the robot's input
and action, any human task, and the run-level metrics. SeamProof never inspects
the live process — it asserts properties over this trace, exactly the way a flight recorder is read
after the fact.

The on-disk shape is intentionally small and platform-neutral so that a UiPath
Maestro audit export, a LangChain callback log, or a hand-written fixture can all
be normalised into it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import TraceError

# Recognised actor categories at a seam. Kept open (free-form strings are
# accepted) but these are the ones the bundled contracts reason about.
ACTOR_TYPES = ("agent", "robot", "human", "router", "system")


@dataclass(frozen=True)
class Event:
    """A single span in a run trace."""

    id: str
    seq: int
    actor: str
    actor_type: str
    type: str
    timestamp: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> Event:
        try:
            return cls(
                id=str(data.get("id", f"e{index}")),
                seq=int(data.get("seq", index)),
                actor=str(data["actor"]),
                actor_type=str(data.get("actor_type", "system")),
                type=str(data["type"]),
                timestamp=data.get("timestamp"),
                attributes=dict(data.get("attributes", {})),
            )
        except KeyError as exc:  # pragma: no cover - defensive
            raise TraceError(f"event #{index} is missing required field {exc}") from exc

    def as_doc(self) -> dict[str, Any]:
        """Flat view used by the assertion engine when matching events."""
        return {
            "id": self.id,
            "seq": self.seq,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "type": self.type,
            "timestamp": self.timestamp,
            **self.attributes,
        }


@dataclass
class Trace:
    """A normalised run trace plus the static context the run executed against."""

    trace_id: str
    process: str
    events: list[Event]
    context: dict[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trace:
        if "events" not in data or not isinstance(data["events"], list):
            raise TraceError("trace must contain an 'events' array")
        events = [Event.from_dict(e, i + 1) for i, e in enumerate(data["events"])]
        events.sort(key=lambda e: e.seq)
        return cls(
            trace_id=str(data.get("trace_id", "unknown")),
            process=str(data.get("process", "unknown")),
            events=events,
            context=dict(data.get("context", {})),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )

    @classmethod
    def load(cls, path: str | Path) -> Trace:
        p = Path(path)
        try:
            data = json.loads(p.read_text())
        except FileNotFoundError as exc:
            raise TraceError(f"trace file not found: {p}") from exc
        except json.JSONDecodeError as exc:
            raise TraceError(f"trace {p} is not valid JSON: {exc}") from exc
        return cls.from_dict(data)

    # -- accessors used while building the evaluation document ---------------

    def first(self, **predicate: Any) -> Event | None:
        """Return the earliest event matching every key in ``predicate``."""
        for event in self.events:
            if _event_matches(event, predicate):
                return event
        return None

    def metrics(self) -> dict[str, Any]:
        """Attributes of the run-level metrics event (cost, cycle time, model)."""
        event = self.first(type="run.metrics")
        return dict(event.attributes) if event else {}

    def event_docs(self) -> list[dict[str, Any]]:
        return [e.as_doc() for e in self.events]


def _event_matches(event: Event, predicate: dict[str, Any]) -> bool:
    for key, want in predicate.items():
        if getattr(event, key, None) != want:
            return False
    return True
