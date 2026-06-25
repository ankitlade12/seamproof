# Contributing to SeamProof

Thanks for your interest in SeamProof. This guide covers how to set up the
project, the conventions we follow, and how to add a new seam.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
make install        # pip install -e ".[dev]"
make check          # ruff + pytest
```

## Project layout

| Path | What lives there |
| --- | --- |
| `src/seamproof/` | The engine: trace model, expression language, evaluators, gate, report, CLI. |
| `contracts/` | Seam contracts for the bundled invoice-exception process. |
| `examples/traces/` | Sample run traces — one golden path plus one injected failure per seam. |
| `scenarios/` | The scenario suite that maps each trace to its expected gate outcome. |
| `tests/` | Unit tests plus the data-driven scenario regression suite. |

## Adding a new assertion kind

1. Write a handler `_assert_<kind>(doc, assertion) -> (passed, detail, evidence)`
   in [`src/seamproof/evaluators.py`](src/seamproof/evaluators.py).
2. Register it in the `_KINDS` dispatch table.
3. Add a unit test in [`tests/test_evaluators.py`](tests/test_evaluators.py).

Assertions never execute arbitrary code — they read the evaluation document
through the reference/condition language in
[`src/seamproof/expr.py`](src/seamproof/expr.py). Keep it that way: a contract
should be reviewable as policy, not trusted as a script.

## Adding a new seam or scenario

1. Drop a contract YAML in `contracts/`.
2. Add a representative run trace in `examples/traces/`.
3. Register the trace and its expected outcome in
   `scenarios/invoice-exception.suite.yaml`. The scenario suite is enforced by
   `tests/test_scenarios.py`, including a guard that every trace on disk is
   covered.

## Conventions

- **Style:** `ruff` governs lint and import order (`make lint`).
- **Tests:** every behavioural change ships with a test; `make test` must be green.
- **Commits:** present-tense, imperative subject lines ("Add cost-SLO seam"),
  scoped to one logical change.

## Reporting bugs and proposing features

Use the issue templates under
[`.github/ISSUE_TEMPLATE`](.github/ISSUE_TEMPLATE). For anything
security-sensitive, follow [SECURITY.md](SECURITY.md) instead of opening a
public issue.
