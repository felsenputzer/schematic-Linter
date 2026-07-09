"""Pull-up resistor: a resistor from a power rail to a signal net that
connects to at least one IC pin."""

from __future__ import annotations

from typing import List

from ..graph.model import CircuitGraph, ComponentKind
from .base import PatternMatch

PATTERN_KIND = "pull_up"


def recognize(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []

    for resistor in graph.components_by_kind(ComponentKind.RESISTOR):
        nets = graph.nets_of(resistor.ref_des)
        if len(nets) != 2:
            continue
        net_a, net_b = graph.get_net(nets[0]), graph.get_net(nets[1])
        if net_a is None or net_b is None:
            continue

        if net_a.is_power and not net_b.is_power:
            power_net, signal_net = net_a, net_b
        elif net_b.is_power and not net_a.is_power:
            power_net, signal_net = net_b, net_a
        else:
            continue

        if signal_net.is_ground or signal_net.is_power:
            continue

        # Note: if another resistor also ties this net to ground, this is
        # topologically also a voltage divider (see voltage_divider.py).
        # We deliberately still report it as a pull-up here too -- patterns
        # stay purely structural/non-exclusive; it's the
        # contention_pull_up_down *rule* that knows a clean divider pair
        # isn't a real contention bug (see that rule's docstring).
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
                nets=[power_net.name, signal_net.name],
                description=(
                    f"{resistor.ref_des} pulls net '{signal_net.name}' up to '{power_net.name}', "
                    f"feeding {', '.join(ic_refs)}"
                ),
                details={
                    "resistor": resistor.ref_des,
                    "power_net": power_net.name,
                    "signal_net": signal_net.name,
                    "ic_refs": ic_refs,
                },
            )
        )

    return matches
