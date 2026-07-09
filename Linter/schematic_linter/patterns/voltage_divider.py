"""Voltage divider: two resistors in series between a source and ground,
with a tap net in the middle."""

from __future__ import annotations

from typing import List

from ..graph.model import CircuitGraph, ComponentKind
from .base import PatternMatch

PATTERN_KIND = "voltage_divider"


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []

    for tap_name, tap_net in graph.nets.items():
        if tap_net.is_power or tap_net.is_ground:
            continue

        resistors = [
            ref for ref in graph.components_on_net(tap_name) if graph.get_component(ref).kind == ComponentKind.RESISTOR
        ]
        if len(resistors) != 2:
            continue

        r1, r2 = resistors
        r1_other = [n for n in graph.nets_of(r1) if n != tap_name]
        r2_other = [n for n in graph.nets_of(r2) if n != tap_name]
        if len(r1_other) != 1 or len(r2_other) != 1:
            continue

        net1, net2 = graph.get_net(r1_other[0]), graph.get_net(r2_other[0])
        if net1 is None or net2 is None:
            continue

        if net1.is_ground and not net2.is_ground:
            bottom_r, top_r, ground_net, source_net = r1, r2, net1, net2
        elif net2.is_ground and not net1.is_ground:
            bottom_r, top_r, ground_net, source_net = r2, r1, net2, net1
        else:
            continue

        matches.append(
            PatternMatch(
                kind=PATTERN_KIND,
                components=[top_r, bottom_r],
                nets=[source_net.name, tap_name, ground_net.name],
                description=(
                    f"Voltage divider: {top_r} from '{source_net.name}' to tap '{tap_name}', "
                    f"{bottom_r} from '{tap_name}' to ground '{ground_net.name}'"
                ),
                details={
                    "top_resistor": top_r,
                    "bottom_resistor": bottom_r,
                    "source_net": source_net.name,
                    "tap_net": tap_name,
                    "ground_net": ground_net.name,
                },
            )
        )

    return matches
