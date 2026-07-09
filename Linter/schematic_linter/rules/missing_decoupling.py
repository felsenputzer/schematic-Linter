"""An IC power pin with no decoupling capacitor on its power net may cause
noise issues. Only runs when the eBOM is present, per spec, since telling
a genuine IC power pin apart from other pins with confidence benefits from
BOM-backed component identity."""

from __future__ import annotations

from typing import List

from ..config import Severity
from ..graph.model import ComponentKind
from .base import Finding, RuleContext

RULE_ID = "missing_decoupling"


def evaluate(ctx: RuleContext) -> List[Finding]:
    if not ctx.has_bom:
        return []

    findings: List[Finding] = []
    decoupled_power_nets = {m.details["power_net"] for m in ctx.matches_of("decoupling_cap")}
    seen_pairs = set()

    for ic in ctx.graph.components_by_kind(ComponentKind.IC):
        for net_name in ctx.graph.nets_of(ic.ref_des):
            net = ctx.graph.get_net(net_name)
            if net is None or not net.is_power:
                continue
            key = (ic.ref_des, net_name)
            if key in seen_pairs or net_name in decoupled_power_nets:
                continue
            seen_pairs.add(key)

            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    severity=Severity.WARNING,
                    title=f"{ic.ref_des} power net '{net_name}' has no decoupling capacitor",
                    description=(
                        f"{ic.ref_des} has a power pin on net '{net_name}', but no capacitor "
                        "directly between that net and ground was found anywhere in the design. "
                        "Missing decoupling can cause supply noise and glitches."
                    ),
                    ref_des=[ic.ref_des],
                    nets=[net_name],
                    pattern_kind="decoupling_cap",
                )
            )

    return findings
