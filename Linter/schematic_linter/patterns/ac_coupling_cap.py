"""AC-coupling capacitor: a capacitor in series between two signal nets
(neither side power or ground) -- distinct from a decoupling cap, which
goes to ground."""

from __future__ import annotations

from typing import List

from ..graph.model import CircuitGraph, ComponentKind
from .base import PatternMatch

PATTERN_KIND = "ac_coupling_cap"


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []

    for cap in graph.components_by_kind(ComponentKind.CAPACITOR):
        nets = graph.nets_of(cap.ref_des)
        if len(nets) != 2:
            continue
        net_a, net_b = graph.get_net(nets[0]), graph.get_net(nets[1])
        if net_a is None or net_b is None:
            continue
        if net_a.is_power or net_a.is_ground or net_b.is_power or net_b.is_ground:
            continue

        matches.append(
            PatternMatch(
                kind=PATTERN_KIND,
                components=[cap.ref_des],
                nets=[net_a.name, net_b.name],
                description=f"{cap.ref_des} AC-couples '{net_a.name}' to '{net_b.name}'",
                details={"capacitor": cap.ref_des, "net_a": net_a.name, "net_b": net_b.name},
            )
        )

    return matches
