"""A component pin named like a power or ground pin that isn't connected
to anything at all is worth flagging -- most other unconnected pins (NC
GPIOs, unused cascade outputs, etc.) are routine, but a floating supply
pin usually is not."""

from __future__ import annotations

from typing import List

from ..config import Severity
from ._pin_naming import GROUND_PIN_NAME_RE, POWER_PIN_NAME_RE
from .base import Finding, RuleContext

RULE_ID = "unconnected_power_pin"


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    for ref_des, component in sorted(ctx.graph.components.items()):
        for pin in component.unconnected_pins:
            if not (POWER_PIN_NAME_RE.match(pin.pin_name) or GROUND_PIN_NAME_RE.match(pin.pin_name)):
                continue

            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    severity=Severity.WARNING,
                    title=f"{ref_des} pin {pin.pin_number} ('{pin.pin_name}') is not connected",
                    description=(
                        f"{ref_des} pin {pin.pin_number} is named '{pin.pin_name}', but the netlist "
                        "has no net connected to it at all. Unlike a spare GPIO, an unconnected "
                        "supply/ground pin is usually a mistake."
                    ),
                    ref_des=[ref_des],
                    nets=[],
                )
            )

    return findings
