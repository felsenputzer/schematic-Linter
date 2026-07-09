"""A net with only a single pin attached is, by definition, not
connecting anything -- almost always a sign of a missing connection or a
leftover from an edit."""

from __future__ import annotations

from typing import List

from ..config import Severity
from ..graph.model import ComponentKind
from .base import Finding, RuleContext

RULE_ID = "floating_single_pin_net"


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    for net_name, net in sorted(ctx.graph.nets.items()):
        if net.is_power or net.is_ground:
            continue
        if net.pin_count != 1:
            continue

        pin = net.pins[0]
        component = ctx.graph.get_component(pin.ref_des)
        kind_label = component.kind.value if component else "component"

        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=Severity.INFO,
                title=f"Net '{net_name}' has only one connection",
                description=(
                    f"Net '{net_name}' connects to only pin {pin.pin_number} ('{pin.pin_name}') of "
                    f"{pin.ref_des} ({kind_label}) and nothing else. This is either a floating/"
                    "unfinished connection or a net that should have been merged with another."
                ),
                ref_des=[pin.ref_des],
                nets=[net_name],
            )
        )

    return findings
