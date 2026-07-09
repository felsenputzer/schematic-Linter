"""Decoupling capacitor: a capacitor directly between a power net and ground."""

from __future__ import annotations

from typing import List

from ..graph.model import CircuitGraph, ComponentKind
from .base import PatternMatch

PATTERN_KIND = "decoupling_cap"


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []

    for cap in graph.components_by_kind(ComponentKind.CAPACITOR):
        nets = graph.nets_of(cap.ref_des)
        if len(nets) != 2:
            continue
        net_a, net_b = graph.get_net(nets[0]), graph.get_net(nets[1])
        if net_a is None or net_b is None:
            continue

        if net_a.is_power and net_b.is_ground:
            power_net, ground_net = net_a, net_b
        elif net_b.is_power and net_a.is_ground:
            power_net, ground_net = net_b, net_a
        else:
            continue

        matches.append(
            PatternMatch(
                kind=PATTERN_KIND,
                components=[cap.ref_des],
                nets=[power_net.name, ground_net.name],
                description=f"{cap.ref_des} decouples '{power_net.name}' to ground '{ground_net.name}'",
                details={
                    "capacitor": cap.ref_des,
                    "power_net": power_net.name,
                    "ground_net": ground_net.name,
                },
            )
        )

    return matches
