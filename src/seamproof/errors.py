"""Exception hierarchy for SeamProof."""
from __future__ import annotations


class SeamProofError(Exception):
    """Base class for every error raised by SeamProof."""


class ContractError(SeamProofError):
    """A seam contract is malformed or references an unknown construct."""


class TraceError(SeamProofError):
    """A run trace could not be parsed or is missing required fields."""
