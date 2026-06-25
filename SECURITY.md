# Security Policy

## Reporting a vulnerability

If you discover a security issue in SeamProof, please **do not open a public
issue**. Instead, report it privately via GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository, or by contacting the maintainer directly.

Please include:

- A description of the issue and its impact
- Steps to reproduce
- Any relevant logs, traces, or proof-of-concept

We aim to acknowledge reports within 72 hours.

## Scope and design notes

SeamProof evaluates **untrusted run traces** against **trusted contracts**:

- **Traces** are treated as data. They are parsed as JSON and never executed.
- **Contracts** use a data-only reference and condition language (see
  [`src/seamproof/expr.py`](src/seamproof/expr.py)). There is no `eval`, no
  dynamic import, and no shell-out anywhere in the evaluation path, so a
  malicious trace cannot cause code execution.

When integrating SeamProof into a pipeline, treat the contracts directory as
trusted input (review contract changes the way you review code) and the trace as
untrusted input (it reflects whatever the system under test produced).
