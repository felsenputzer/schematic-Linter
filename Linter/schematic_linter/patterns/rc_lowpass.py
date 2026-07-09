"""RC low-pass filter: a resistor followed by a capacitor to ground."""

from __future__ import annotations

from typing import List

from ..graph.model import CircuitGraph, ComponentKind
from .base import PatternMatch

PATTERN_KIND = "rc_lowpass"


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []

    for mid_name, mid_net in graph.nets.items():
        if mid_net.is_power or mid_net.is_ground:
            continue

        refs_on_mid = graph.components_on_net(mid_name)
        resistors = [r for r in refs_on_mid if graph.get_component(r).kind == ComponentKind.RESISTOR]
        capacitors = [c for c in refs_on_mid if graph.get_component(c).kind == ComponentKind.CAPACITOR]
        if not resistors or not capacitors:
            continue

        for resistor in resistors:
            r_other = [n for n in graph.nets_of(resistor) if n != mid_name]
            if len(r_other) != 1:
                continue
            source_net = graph.get_net(r_other[0])
            if source_net is None or source_net.is_ground:
                continue

            for capacitor in capacitors:
                c_other = [n for n in graph.nets_of(capacitor) if n != mid_name]
                if len(c_other) != 1:
                    continue
                ground_candidate = graph.get_net(c_other[0])
                if ground_candidate is None or not ground_candidate.is_ground:
                    continue

                matches.append(
                    PatternMatch(
                        kind=PATTERN_KIND,
                        components=[resistor, capacitor],
                        nets=[source_net.name, mid_name, ground_candidate.name],
                        description=(
                            f"RC low-pass: {resistor} from '{source_net.name}' to '{mid_name}', "
                            f"{capacitor} from '{mid_name}' to ground '{ground_candidate.name}'"
                        ),
                        details={
                            "resistor": resistor,
                            "capacitor": capacitor,
                            "source_net": source_net.name,
                            "mid_net": mid_name,
                            "ground_net": ground_candidate.name,
                        },
                    )
                )

    return matches
