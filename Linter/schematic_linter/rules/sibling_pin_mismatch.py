"""Flags a pin that's wired differently from the same-named pin on sibling
instances of the identical part.

When a part repeats 3+ times in a design (e.g. three cascaded 74HC595 shift
registers), same-named control pins are normally bussed to the same net
across every instance (OE, RESET, LCK/SCK, ...). If all-but-one instance
agree and a single instance's pin lands on a different net, that's a strong,
purely structural signal of a wiring/pin-swap mistake -- no per-part
pin-function or datasheet knowledge required, only the repetition already
present in the design.

This deliberately requires a *unanimous-minus-one* majority (not just "most"
instances agreeing) to keep the false-positive rate low: legitimate stuffing
variants that split a group into two or more camps are left alone.

Nets are canonicalized through inline 2-pin series passives (see
``graph/net_resolve.py``) before comparison, so a component sitting behind a
series-termination resistor isn't mistaken for a mismatch.

This caught a real, unambiguous case in the bundled sample netlist: ``U04``
pin 13 (``OE``) is wired to net ``OUT2_IN3`` (the chain net that should have
gone to pin 14 ``A``) while ``U02``/``U03`` correctly share ``OE`` on
``ENABLE``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from ..config import (
    SIBLING_GROUP_MIN_SIZE,
    SIBLING_MIN_COMMON_PIN_NAMES,
    SIBLING_NET_RESOLVE_MAX_HOPS,
    Severity,
)
from ..graph.model import CircuitGraph, Component, Pin
from ..graph.net_resolve import canonicalize_net
from .base import Finding, RuleContext

RULE_ID = "sibling_pin_mismatch"


def _net_for_pin_name(graph: CircuitGraph, ref_des: str, pin_name: str) -> Tuple[Optional[str], Optional[Pin]]:
    for net_name in graph.nets_of(ref_des):
        for pin in graph.pins_on_edge(ref_des, net_name):
            if pin.pin_name == pin_name:
                return net_name, pin
    return None, None


def _common_pin_names(components: List[Component]) -> set:
    pin_name_sets = [
        {p.pin_name for p in c.pins} | {p.pin_name for p in c.unconnected_pins} for c in components
    ]
    if not pin_name_sets:
        return set()
    return set.intersection(*pin_name_sets)


def _group_by_comp_type(graph: CircuitGraph) -> Dict[str, List[Component]]:
    groups: Dict[str, List[Component]] = defaultdict(list)
    for component in graph.components.values():
        for comp_type in component.comp_types:
            groups[comp_type].append(component)
    return groups


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    for comp_type, components in sorted(_group_by_comp_type(ctx.graph).items()):
        if len(components) < SIBLING_GROUP_MIN_SIZE:
            continue

        components = sorted(components, key=lambda c: c.ref_des)
        common_pin_names = _common_pin_names(components)
        if len(common_pin_names) < SIBLING_MIN_COMMON_PIN_NAMES:
            continue

        for pin_name in sorted(common_pin_names):
            # ref_des -> (literal net, canonical net, Pin)
            per_component: Dict[str, Tuple[str, str, Pin]] = {}
            for component in components:
                net_name, pin = _net_for_pin_name(ctx.graph, component.ref_des, pin_name)
                if net_name is None:
                    continue  # unconnected -- covered by other rules
                canonical = canonicalize_net(ctx.graph, net_name, SIBLING_NET_RESOLVE_MAX_HOPS)
                per_component[component.ref_des] = (net_name, canonical, pin)

            total = len(per_component)
            if total < SIBLING_GROUP_MIN_SIZE:
                continue

            canonical_counts = Counter(v[1] for v in per_component.values())
            common_canonical, common_count = canonical_counts.most_common(1)[0]
            differing = {ref: v for ref, v in per_component.items() if v[1] != common_canonical}

            if common_count != total - 1 or len(differing) != 1:
                continue

            outlier_ref, (outlier_net, _outlier_canonical, outlier_pin) = next(iter(differing.items()))
            sibling_refs = [ref for ref in per_component if ref != outlier_ref]
            sibling_literal_nets = {per_component[ref][0] for ref in sibling_refs}
            common_net_display = (
                next(iter(sibling_literal_nets))
                if len(sibling_literal_nets) == 1
                else f"(effectively) {common_canonical}"
            )

            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    severity=Severity.WARNING,
                    title=(
                        f"{outlier_ref} pin {outlier_pin.pin_number} ('{pin_name}') wired differently "
                        f"from sibling {comp_type} instances"
                    ),
                    description=(
                        f"{outlier_ref} pin {outlier_pin.pin_number} ('{pin_name}') connects to net "
                        f"'{outlier_net}', but the other {len(sibling_refs)} instance(s) of the same part "
                        f"({comp_type}) -- {', '.join(sibling_refs)} -- all connect their '{pin_name}' pin "
                        f"to net '{common_net_display}'. This looks like a possible wiring/pin-swap "
                        "mistake; verify against the schematic."
                    ),
                    ref_des=[outlier_ref] + sibling_refs,
                    nets=[outlier_net] + sorted(sibling_literal_nets - {outlier_net}),
                    details={"pin_name": pin_name, "comp_type": comp_type},
                )
            )

    return findings
