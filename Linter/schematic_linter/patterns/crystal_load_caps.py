"""Crystal/oscillator with its load capacitors (each resonator leg
optionally decoupled to ground by a capacitor)."""

from __future__ import annotations

from typing import List

from ..graph.model import CircuitGraph, ComponentKind
from .base import PatternMatch

PATTERN_KIND = "crystal_load_caps"


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []

    for crystal in graph.components_by_kind(ComponentKind.CRYSTAL):
        signal_nets = [
            n
            for n in graph.nets_of(crystal.ref_des)
            if graph.get_net(n) is not None and not graph.get_net(n).is_ground and not graph.get_net(n).is_power
        ]
        if not signal_nets:
            continue

        load_caps: List[str] = []
        for net_name in signal_nets:
            for ref in graph.components_on_net(net_name):
                if ref == crystal.ref_des:
                    continue
                component = graph.get_component(ref)
                if component is None or component.kind != ComponentKind.CAPACITOR:
                    continue
                other_nets = [n for n in graph.nets_of(ref) if n != net_name]
                if len(other_nets) != 1:
                    continue
                other_net = graph.get_net(other_nets[0])
                if other_net is not None and other_net.is_ground:
                    load_caps.append(ref)

        matches.append(
            PatternMatch(
                kind=PATTERN_KIND,
                components=[crystal.ref_des] + load_caps,
                nets=signal_nets,
                description=(
                    f"Crystal {crystal.ref_des} has {len(load_caps)} load capacitor(s) to ground: "
                    f"{', '.join(load_caps) if load_caps else 'none found'}"
                ),
                details={
                    "crystal": crystal.ref_des,
                    "load_caps": load_caps,
                    "signal_nets": signal_nets,
                },
            )
        )

    return matches
