# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-25

UiPath integration — connect the engine to Automation Cloud at both ends.

### Added
- `ingest.py`: ingest a UiPath Maestro **OpenTelemetry** (OTLP/JSON) export into a
  SeamProof trace, with recursive decoding of typed OTLP attribute values and a
  `run.context` span lifted into the trace context.
- `publish.py`: publish the gate result to **UiPath Test Manager**, via the
  official `uipath` SDK when installed (`seamproof[uipath]`) or a stdlib REST
  transport using `UIPATH_URL` + `UIPATH_ACCESS_TOKEN`; `--dry-run` previews the
  payload offline.
- CLI: `seamproof ingest`, `seamproof publish`, and `seamproof check --otel/--context`.
- A sample Maestro OTLP export (`examples/otel/`) reproducing the Seam 1 case.

### Changed
- Version is now sourced from `seamproof/_version.py` (single source of truth).

## [0.1.0] - 2026-06-25

Initial release — the seam-testing engine and release gate.

### Added
- Trace model that normalises a Maestro-style run into ordered events plus
  static context.
- Data-only contract language: dotted-path references with `[*]` wildcards and
  reducers, and an `any`/`all`/`not` condition tree.
- Six assertion kinds: `equals`, `not_equals`, `in_set`, `matches`, `range`, and
  `requires_event` (with `when` guard and `before` ordering).
- Release gate with `blocking` and `advisory` severities and a CI-native exit
  code.
- Report renderers for `text`, `markdown`, `json`, and JUnit `xml`.
- `seamproof check` CLI.
- Invoice-exception system-under-test: three seam contracts, five sample run
  traces, and a scenario suite.
- Test suite (unit + data-driven scenarios) and GitHub Actions CI.

[Unreleased]: https://github.com/ankitlade12/seamproof/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ankitlade12/seamproof/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ankitlade12/seamproof/releases/tag/v0.1.0
