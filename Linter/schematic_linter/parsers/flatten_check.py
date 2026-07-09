"""Guards against running the analysis on a non-flattened netlist.

Why this is currently a stub
-----------------------------
A flattened netlist assigns each reference designator a single, globally
resolved identity. A tempting heuristic is: "if the same ref-des is bound to
more than one distinct internal placement/instance id, the design wasn't
flattened". That heuristic was tried against the known-good sample netlist
(``TestData/Projekt1/TestDesign.ndf``) during design of this module and it
produces **false positives** on entirely legitimate, fully flattened data:

* Multi-gate ICs (e.g. the dual op-amp ``081708U01``) get a distinct
  internal instance id per gate/symbol placement, even though they share
  one physical ref-des.
* Multi-pin connectors (e.g. ``J01``-``J03``) were observed with a distinct
  instance id *per pin* in this export.

Using that heuristic would therefore reject valid designs, which is worse
than not checking at all (the whole point of this check is trustworthiness).
Per project decision, this check is shipped as an explicit, honest stub
until a real non-flattened/hierarchical sample netlist is available to
design and validate a reliable heuristic against.

TODO(flatten-detection): once a real non-flattened sample is available,
replace the body of ``check_flattened`` with a validated heuristic (see
project plan for candidate signals) and add regression tests for both the
good and bad sample.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .netlist_parser import PinRecord


class NonFlattenedNetlistError(Exception):
    """Raised when the netlist is confidently identified as non-flattened."""

    def __init__(self, message: str, offending_ref_des: List[str] | None = None):
        super().__init__(message)
        self.offending_ref_des = offending_ref_des or []


@dataclass(frozen=True)
class FlattenCheckResult:
    is_flattened: bool
    notes: List[str] = field(default_factory=list)


def check_flattened(pin_records: List[PinRecord]) -> FlattenCheckResult:
    """Best-effort sanity check that the netlist is a flat, fully-exported one.

    Currently always reports the netlist as flattened (no-op pass-through);
    see module docstring for why a stronger heuristic isn't implemented yet.
    Kept as its own pipeline step (rather than removed outright) so a real
    heuristic can be dropped in later without touching any other module,
    and so the pipeline already has the correct "reject before analysis"
    control flow in place via ``NonFlattenedNetlistError``.
    """

    if not pin_records:
        raise NonFlattenedNetlistError("Netlist contains no pin records to analyze")

    return FlattenCheckResult(
        is_flattened=True,
        notes=[
            "Non-flattened netlist detection is currently a provisional "
            "stub (always passes) -- see flatten_check.py for details."
        ],
    )
