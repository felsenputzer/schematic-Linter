"""Canonicalizes a net through inline 2-pin series passives.

Two nets separated only by a series resistor or inductor (e.g. a clock-line
series-termination resistor, a ferrite bead) are, for most structural
comparisons, "the same signal" -- the resistor doesn't change *what* the
signal is, only its edge rate/impedance. Capacitors are deliberately
excluded: a series capacitor AC-couples two nets that are legitimately
different DC nodes (see ``patterns/ac_coupling_cap.py``), so collapsing
through one would hide a real distinction.

This is used by ``rules/sibling_pin_mismatch.py`` so that a component sitting
behind a series-termination resistor isn't mistaken for a wiring mismatch
against its siblings.
"""

from __future__ import annotations

from typing import Optional

from .model import CircuitGraph, ComponentKind, Net

_PASSTHROUGH_KINDS = (ComponentKind.RESISTOR, ComponentKind.INDUCTOR)


def _passthrough_component_ref(graph: CircuitGraph, net: Net) -> Optional[str]:
    """If ``net`` is a simple 2-pin pass-through (one side is a bare 2-pin
    resistor/inductor), return that component's ref-des; otherwise ``None``.
    """

    if net.pin_count != 2:
        return None

    for pin in net.pins:
        component = graph.get_component(pin.ref_des)
        if component is not None and component.kind in _PASSTHROUGH_KINDS and len(component.pins) == 2:
            return component.ref_des
    return None


def canonicalize_net(graph: CircuitGraph, net_name: str, max_hops: int) -> str:
    """Resolve ``net_name`` through inline 2-pin series passives.

    Walks up to ``max_hops`` times: if the current net connects to exactly
    two things and one of them is a simple 2-pin resistor/inductor, hop to
    the net on the passive's other side. Stops early if the net isn't a pure
    pass-through, if the passive's other side is ambiguous, or if a cycle
    would result.
    """

    current = net_name
    visited = {current}

    for _ in range(max_hops):
        net = graph.get_net(current)
        if net is None:
            break

        passive_ref = _passthrough_component_ref(graph, net)
        if passive_ref is None:
            break

        other_nets = [n for n in graph.nets_of(passive_ref) if n != current]
        if len(other_nets) != 1:
            break

        next_net = other_nets[0]
        if next_net in visited:
            break

        visited.add(next_net)
        current = next_net

    return current
