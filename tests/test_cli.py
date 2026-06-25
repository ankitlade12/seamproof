"""End-to-end CLI tests, exercising exit codes — the gate's contract with CI."""
from __future__ import annotations

from pathlib import Path

from seamproof.cli import main

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = str(ROOT / "contracts")
TRACES = ROOT / "examples" / "traces"


def test_go_path_exits_zero(capsys):
    code = main(["check", "-c", CONTRACTS, "-t", str(TRACES / "golden_happy_path.json")])
    assert code == 0
    assert "GATE: GO" in capsys.readouterr().out


def test_blocking_failure_exits_one(capsys):
    code = main(["check", "-c", CONTRACTS, "-t", str(TRACES / "seam1_amount_mismatch.json")])
    assert code == 1
    assert "GATE: NO-GO" in capsys.readouterr().out


def test_advisory_failure_does_not_block(capsys):
    code = main(["check", "-c", CONTRACTS, "-t", str(TRACES / "seam3_cost_regression.json")])
    assert code == 0  # advisory seam fails but the gate stays GO
    assert "advisory" in capsys.readouterr().out.lower()


def test_no_fail_flag_forces_zero():
    code = main(["check", "-c", CONTRACTS, "-t", str(TRACES / "seam2_skipped_approval.json"), "--no-fail"])
    assert code == 0


def test_out_writes_file(tmp_path, capsys):
    out = tmp_path / "report.xml"
    code = main([
        "check", "-c", CONTRACTS, "-t", str(TRACES / "seam1_amount_mismatch.json"),
        "-f", "junit", "-o", str(out),
    ])
    assert code == 1
    assert out.exists() and out.read_text().lstrip().startswith("<?xml")
    assert "Report written to" in capsys.readouterr().out


def test_missing_trace_is_clean_error(capsys):
    code = main(["check", "-c", CONTRACTS, "-t", str(TRACES / "does_not_exist.json")])
    assert code == 2
    assert "error" in capsys.readouterr().err.lower()
