"""Shared fixtures: filesystem paths to the bundled contracts and traces."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
    return ROOT / "contracts"


@pytest.fixture(scope="session")
def traces_dir() -> Path:
    return ROOT / "examples" / "traces"
