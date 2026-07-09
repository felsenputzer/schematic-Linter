"""Series termination resistor: a resistor in series between a signal
source and an IC input pin (neither side is a power/ground net)."""

from __future__ import annotations

import re
from typing import List, Tuple

from ..graph.model import CircuitGraph, ComponentKind, Net
from .base import PatternMatch

PATTERN_KIND = "series_termination"

_INPUT_LIKE_PIN_RE = re.compile(r"IN[-+]?$|^IN\b|SDA|SCL|CLK|RESET|^RX|^EN\b|^A\d+$|^D\d+$", re.I)


def _ic_input_hits(graph: CircuitGraph, net: Net, exclude_ref: str) -> List[Tuple[str, str]]:
    hits = []
    for ref in graph.components_on_net(net.name):
        if ref == exclude_ref:
            continue
        component = graph.get_component(ref)
        if component is None or component.kind != ComponentKind.IC:
            continue
        for pin in graph.pins_on_edge(ref, net.name):
            if _INPUT_LIKE_PIN_RE.search(pin.pin_name):
                hits.append((ref, pin.pin_name))
    return hits


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []
    seen_resistors = set()

    for resistor in graph.components_by_kind(ComponentKind.RESISTOR):
        if resistor.ref_des in seen_resistors:
            continue
        nets = graph.nets_of(resistor.ref_des)
        if len(nets) != 2:
            continue
        net_a, net_b = graph.get_net(nets[0]), graph.get_net(nets[1])
        if net_a is None or net_b is None:
            continue
        if net_a.is_power or net_a.is_ground or net_b.is_power or net_b.is_ground:
            continue  # that would be a pull-up/pull-down, not series termination

        for source_net, dest_net in ((net_a, net_b), (net_b, net_a)):
            ic_hits = _ic_input_hits(graph, dest_net, resistor.ref_des)
            if not ic_hits:
                continue
            other_on_source = [ref for ref in graph.components_on_net(source_net.name) if ref != resistor.ref_des]
            if not other_on_source:
                continue  # source side must actually be driven by something

            ic_refs = sorted({ref for ref, _pin in ic_hits})
            matches.append(
                PatternMatch(
                    kind=PATTERN_KIND,
                    components=[resistor.ref_des] + ic_refs,
                    nets=[source_net.name, dest_net.name],
                    description=(
                        f"{resistor.ref_des} series-terminates '{source_net.name}' into "
                        f"{', '.join(ic_refs)} on '{dest_net.name}'"
                    ),
                    details={
                        "resistor": resistor.ref_des,
                        "source_net": source_net.name,
                        "destination_net": dest_net.name,
                        "ic_refs": ic_refs,
                    },
                )
            )
            seen_resistors.add(resistor.ref_des)
            break

    return matches
