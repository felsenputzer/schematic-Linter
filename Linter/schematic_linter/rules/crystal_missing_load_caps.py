"""A crystal/oscillator normally needs two load capacitors (one per
resonator leg, to ground). Fewer than that is worth a second look."""

from __future__ import annotations

from typing import List

from ..config import Severity
from .base import Finding, RuleContext

RULE_ID = "crystal_missing_load_caps"

_EXPECTED_LOAD_CAPS = 2


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    for m in ctx.matches_of("crystal_load_caps"):
        load_caps = m.details["load_caps"]
        if len(load_caps) >= _EXPECTED_LOAD_CAPS:
            continue

        crystal = m.details["crystal"]
        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=Severity.WARNING,
                title=f"Crystal {crystal} has {len(load_caps)}/{_EXPECTED_LOAD_CAPS} load capacitors",
                description=(
                    f"Crystal {crystal} was found with only {len(load_caps)} load capacitor(s) "
                    f"({', '.join(load_caps) if load_caps else 'none'}) to ground on its resonator "
                    f"legs {', '.join(m.details['signal_nets'])}. Most crystal oscillator circuits "
                    "need a load capacitor on each leg for correct startup and frequency accuracy."
                ),
                ref_des=[crystal] + load_caps,
                nets=m.details["signal_nets"],
                pattern_kind="crystal_load_caps",
            )
        )

    return findings
