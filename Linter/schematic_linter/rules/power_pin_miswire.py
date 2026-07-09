"""A pin named like a power pin (VCC/VDD/...) tied to a net tagged GROUND,
or a pin named like a ground pin (GND/VSS/...) tied to a net tagged POWER,
is almost certainly a wiring mistake -- not a topology pattern, just a
direct, high-confidence structural check against the netlist's own
POWER/GROUND tagging.

This rule caught a real, unambiguous case in the bundled sample netlist:
``U03`` pin 16 is named ``VCC`` but is wired to the ``GND`` net (compare
with the otherwise-identical ``U04`` pin 16, correctly wired to
``IPSU_5V``).
"""

from __future__ import annotations

from typing import List

from ..config import Severity
from ._pin_naming import GROUND_PIN_NAME_RE, POWER_PIN_NAME_RE
from .base import Finding, RuleContext

RULE_ID = "power_pin_miswire"


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    for ref_des, component in sorted(ctx.graph.components.items()):
        for net_name in ctx.graph.nets_of(ref_des):
            net = ctx.graph.get_net(net_name)
            if net is None or not (net.is_ground or net.is_power):
                continue

            for pin in ctx.graph.pins_on_edge(ref_des, net_name):
                if POWER_PIN_NAME_RE.match(pin.pin_name) and net.is_ground:
                    findings.append(
                        Finding(
                            rule_id=RULE_ID,
                            severity=Severity.ERROR,
                            title=f"{ref_des} pin {pin.pin_number} ('{pin.pin_name}') tied to ground net '{net_name}'",
                            description=(
                                f"{ref_des} pin {pin.pin_number} is named '{pin.pin_name}' (a supply "
                                f"pin) but is connected to '{net_name}', which the netlist tags as a "
                                "GROUND net. This looks like a power/ground wiring mistake."
                            ),
                            ref_des=[ref_des],
                            nets=[net_name],
                        )
                    )
                elif GROUND_PIN_NAME_RE.match(pin.pin_name) and net.is_power:
                    findings.append(
                        Finding(
                            rule_id=RULE_ID,
                            severity=Severity.ERROR,
                            title=f"{ref_des} pin {pin.pin_number} ('{pin.pin_name}') tied to power net '{net_name}'",
                            description=(
                                f"{ref_des} pin {pin.pin_number} is named '{pin.pin_name}' (a ground "
                                f"pin) but is connected to '{net_name}', which the netlist tags as a "
                                "POWER net. This looks like a power/ground wiring mistake."
                            ),
                            ref_des=[ref_des],
                            nets=[net_name],
                        )
                    )

    return findings
