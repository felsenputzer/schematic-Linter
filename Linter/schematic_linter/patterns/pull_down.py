"""Pull-down resistor: a resistor from ground to a signal net that connects
to at least one IC pin."""

from __future__ import annotations

from typing import List

from ..graph.model import CircuitGraph, ComponentKind
from .base import PatternMatch

PATTERN_KIND = "pull_down"


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []

    for resistor in graph.components_by_kind(ComponentKind.RESISTOR):
        nets = graph.nets_of(resistor.ref_des)
        if len(nets) != 2:
            continue
        net_a, net_b = graph.get_net(nets[0]), graph.get_net(nets[1])
        if net_a is None or net_b is None:
            continue

        if net_a.is_ground and not net_b.is_ground:
            ground_net, signal_net = net_a, net_b
        elif net_b.is_ground and not net_a.is_ground:
            ground_net, signal_net = net_b, net_a
        else:
            continue

        if signal_net.is_ground or signal_net.is_power:
            continue

        # See pull_up.py's note on why divider legs are still reported here.
        ic_refs = [
            ref
            for ref in graph.components_on_net(signal_net.name)
            if ref != resistor.ref_des
            and graph.get_component(ref) is not None
            and graph.get_component(ref).kind == ComponentKind.IC
        ]
        if not ic_refs:
            continue

        matches.append(
            PatternMatch(
                kind=PATTERN_KIND,
                components=[resistor.ref_des] + ic_refs,
                nets=[ground_net.name, signal_net.name],
                description=(
                    f"{resistor.ref_des} pulls net '{signal_net.name}' down to '{ground_net.name}', "
                    f"feeding {', '.join(ic_refs)}"
                ),
                details={
                    "resistor": resistor.ref_des,
                    "ground_net": ground_net.name,
                    "signal_net": signal_net.name,
                    "ic_refs": ic_refs,
                },
            )
        )

    return matches
