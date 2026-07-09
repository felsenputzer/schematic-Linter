"""A voltage divider whose tap net connects to nothing but the two
resistors is unloaded -- probably an incomplete design."""

from __future__ import annotations

from typing import List

from ..config import Severity
from .base import Finding, RuleContext

RULE_ID = "unloaded_divider"


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    for m in ctx.matches_of("voltage_divider"):
        tap_net = m.details["tap_net"]
        net = ctx.graph.get_net(tap_net)
        if net is None:
            continue
        connected_refs = set(ctx.graph.components_on_net(tap_net))
        expected_refs = {m.details["top_resistor"], m.details["bottom_resistor"]}
        if connected_refs - expected_refs:
            continue  # something else is also on the tap -- it's loaded

        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=Severity.INFO,
                title=f"Voltage divider tap '{tap_net}' is unloaded",
                description=(
                    f"The divider formed by {m.details['top_resistor']} and "
                    f"{m.details['bottom_resistor']} has its tap net '{tap_net}' connected to "
                    "nothing else. A divider with no load is unusual unless it feeds an "
                    "off-sheet connector/test point, or the design is still incomplete."
                ),
                ref_des=[m.details["top_resistor"], m.details["bottom_resistor"]],
                nets=[tap_net],
                pattern_kind="voltage_divider",
            )
        )

    return findings
