"""A pull resistor whose eBOM value resolves to 0 ohm is likely a jumper,
not a real pull -- flag for human review rather than assuming either way."""

from __future__ import annotations

from typing import List, Optional

from ..config import NOTE_VALUE_UNKNOWN, ZERO_OHM_THRESHOLD, Severity
from ..graph.model import Component
from .base import Finding, RuleContext

RULE_ID = "zero_ohm_pull_review"


def _finding_for(ctx: RuleContext, kind: str, label: str) -> List[Finding]:
    findings: List[Finding] = []
    seen_resistors = set()

    for m in ctx.matches_of(kind):
        resistor_ref = m.details["resistor"]
        if resistor_ref in seen_resistors:
            continue
        seen_resistors.add(resistor_ref)

        component: Optional[Component] = ctx.graph.get_component(resistor_ref)
        if component is None:
            continue

        if component.value_source != "ebom" or component.value is None:
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    severity=Severity.INFO,
                    title=f"{label.capitalize()} resistor {resistor_ref} has an unknown value",
                    description=(
                        f"{resistor_ref} acts as a {label} on net '{m.details['signal_net']}'. "
                        f"Structurally, a 0\u03a9 jumper looks identical to a real {label} resistor "
                        f"-- {NOTE_VALUE_UNKNOWN}."
                    ),
                    ref_des=[resistor_ref],
                    nets=[m.details["signal_net"]],
                    pattern_kind=kind,
                    note=NOTE_VALUE_UNKNOWN,
                )
            )
            continue

        if component.value.unit == "ohm" and component.value.magnitude <= ZERO_OHM_THRESHOLD:
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    severity=Severity.WARNING,
                    title=f"{label.capitalize()} resistor {resistor_ref} is 0\u03a9 (likely a jumper)",
                    description=(
                        f"{resistor_ref} is populated as a {label} on net '{m.details['signal_net']}' "
                        f"but its eBOM value is {component.value.display}. This is almost certainly "
                        "being used as a jumper/link rather than an actual pull resistor -- please "
                        "confirm this is intentional."
                    ),
                    ref_des=[resistor_ref],
                    nets=[m.details["signal_net"]],
                    pattern_kind=kind,
                )
            )

    return findings


def evaluate(ctx: RuleContext) -> List[Finding]:
    return _finding_for(ctx, "pull_up", "pull-up") + _finding_for(ctx, "pull_down", "pull-down")
