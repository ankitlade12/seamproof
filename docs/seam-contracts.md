# Seam contracts reference

A **seam contract** declares the properties the *receiving* actor at a boundary
depends on. This document is the full reference for the contract language and the
three seams shipped for the invoice-exception process.

## File shape

```yaml
id: seam-1
name: Agent to Robot data contract
description: One paragraph on what fails at this seam and why it matters.
severity: blocking          # or: advisory
boundary:
  from: recon-agent
  to: posting-robot
handoff:
  source: { type: robot.input }   # the event whose attributes become `handoff`
assertions:
  - id: amount-equals-line-items
    kind: equals
    description: Posted amount must equal the sum of the line items.
    left:  { ref: handoff.amount }
    right: { ref: "handoff.line_items[*].amount", reduce: sum }
    tolerance: 0.005
```

## Operands

Every assertion field that takes a value accepts an **operand**:

| Operand | Meaning |
| --- | --- |
| `{ ref: "handoff.amount" }` | Resolve a dotted path against the evaluation document. |
| `{ ref: "handoff.line_items[*].amount", reduce: sum }` | Resolve a wildcard path to a list, then fold it. |
| `{ const: 10000 }` | A literal value. |
| `4200` / `"USD"` / `true` | A bare literal (shorthand for `const`). |

**Paths** support nested keys (`context.po.currency`), list indexes
(`line_items[0].amount`), and the `[*]` wildcard, which fans the path across a
list. **Reducers**: `sum`, `count`, `min`, `max`, `avg`. A path that does not
resolve yields a *missing* sentinel that compares unequal to everything.

The evaluation document has four roots: `handoff`, `context`, `events`,
`metrics` (see [architecture.md](architecture.md)).

## Assertion kinds

| Kind | Fields | Passes when |
| --- | --- | --- |
| `equals` | `left`, `right`, `tolerance?` | operands are equal (within `tolerance` if numeric) |
| `not_equals` | `left`, `right` | operands differ |
| `in_set` | `value`, `set` | `value` is a member of the list `set` |
| `matches` | `value`, `pattern` | `value` is a string matching the regex `pattern` |
| `range` | `value`, `min?`, `max?`, `exclusive_min?`, `exclusive_max?` | `value` is a number within the bounds |
| `requires_event` | `when?`, `event`, `before?` | when `when` holds, a matching `event` exists (before `before`, if given) |

### Conditions (the `when` clause)

`requires_event.when` is a boolean tree:

```yaml
when:
  any:                              # any | all | not
    - { gte: [ { ref: handoff.amount }, { ref: context.human_review_floor } ] }
    - { lt:  [ { ref: handoff.confidence }, { ref: context.min_confidence } ] }
    - { eq:  [ { ref: handoff.exception_flagged }, true ] }
```

Comparators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`. Combinators: `any`,
`all`, `not`. Each comparator takes `[left, right]` operands.

### Event selectors (the `event` / `before` clause)

```yaml
event:
  actor_type: human          # match on any event field
  type: human.decision
  where: { status: approved } # match on event attributes
before:
  type: robot.action          # the required event must occur before this one
```

## Severity

- **blocking** (default): a failure here vetoes the release — the gate returns
  NO-GO and `seamproof check` exits `1`.
- **advisory**: a failure is reported (and marked in every output format) but the
  gate stays GO and the CLI exits `0`. Use it for SLO drift you want visible
  before you enforce it.

## The three shipped seams

### Seam 1 — Agent → Robot (silent corruption) · blocking

The robot faithfully posts whatever the agent hands it. This contract pins the
invariants the robot cannot check itself:

- `amount == sum(line_items)` (tolerance `0.005`)
- `currency == PO.currency`
- `vendor_id ∈ approved_vendor_master`
- `amount > 0`

**Caught:** an agent that emits valid JSON with a transposed/hallucinated total
(`5400` vs. line items summing to `4200`).

### Seam 2 — Routing → Human (skipped checkpoint) · blocking

When policy requires a human — amount at/above the review floor, confidence below
threshold, or an exception flag — an **approved** `human.decision` must exist and
fire **before** the robot posts.

**Caught:** a `$9,950` invoice in the `$9,000–$10,000` review band that auto-posts
around the approval the policy required.

### Seam 3 — Cost / cycle-time SLO · advisory

Non-functional drift: `metrics.cost_usd ≤ sla.max_cost_usd` and
`metrics.cycle_seconds ≤ sla.max_cycle_seconds`.

**Caught:** a model swap that keeps outputs correct but doubles cost-per-run and
pushes cycle time past the SLO. Reported as a warning; does not block.
