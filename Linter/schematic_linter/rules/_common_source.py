"""Shared helpers for reasoning about a resistor that feeds a node shared by
two or more otherwise-independent RC filter branches (a "common source
impedance" -- current drawn by either branch develops a voltage drop that's
visible to the other, coupling measurements that were meant to be
independent).

Named with a leading underscore (and deliberately defining no ``evaluate``
function) so the rule registry's auto-discovery skips it -- it's a helper
module, not a rule itself. Used by both ``shared_rc_resistor`` (to avoid
mistaking a plain decoupling cap on a resistor's low-impedance source side
for a second, independent filter tap) and ``shared_source_resistor`` (which
flags the feed resistor itself).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from ..config import ZERO_OHM_THRESHOLD
from ..graph.model import Component, ComponentKind
from ..patterns.base import PatternMatch
from .base import RuleContext

_PASSIVE_KINDS = {ComponentKind.RESISTOR, ComponentKind.CAPACITOR, ComponentKind.INDUCTOR}


def _terminates_at_a_load(ctx: RuleContext, net: str) -> bool:
    """True if ``net`` hosts something other than plain R/L/C passives --
    i.e. it looks like an actual measurement/signal endpoint (an IC pin, a
    connector, a test point, ...) rather than a net that just continues on
    through more filtering/biasing components. Used to tell a genuine RC
    filter *branch* (terminates at a load) apart from a resistor that merely
    *feeds* a shared node from further upstream (which will itself often
    have its own decoupling cap, but no load directly on it)."""

    for ref in ctx.graph.components_on_net(net):
        component = ctx.graph.get_component(ref)
        if component is not None and component.kind not in _PASSIVE_KINDS:
            return True
    return False


def branch_groups(ctx: RuleContext, matches: List[PatternMatch]) -> Dict[str, List[str]]:
    """Maps each net that is the ``source_net`` of 2+ distinct resistors
    across ``rc_lowpass`` matches whose ``mid_net`` terminates at an actual
    load (i.e. a fan-out point feeding two or more independently-filtered
    measurement branches) to the sorted list of those resistors.

    Matches whose ``mid_net`` doesn't terminate at a load are excluded here
    -- those are typically a resistor that itself feeds the shared node from
    further upstream (and so has its own valid-looking ``rc_lowpass`` match
    thanks to a decoupling cap on its far side), not a genuine branch."""

    by_source = defaultdict(set)
    for m in matches:
        if not _terminates_at_a_load(ctx, m.details["mid_net"]):
            continue
        by_source[m.details["source_net"]].add(m.details["resistor"])
    return {net: sorted(refs) for net, refs in by_source.items() if len(refs) >= 2}


def feed_resistors(ctx: RuleContext, net: str, exclude: List[str]) -> List[str]:
    """Resistors feeding ``net`` from elsewhere -- i.e. not one of the
    ``exclude``d branch resistors fanning out *from* it -- with their other
    terminal on a non-ground net."""

    feeds: List[str] = []
    for ref in ctx.graph.components_on_net(net):
        if ref in exclude:
            continue
        component = ctx.graph.get_component(ref)
        if component is None or component.kind != ComponentKind.RESISTOR:
            continue
        other_nets = ctx.graph.other_pins_of_component(ref, net)
        if len(other_nets) != 1:
            continue
        other_net = ctx.graph.get_net(other_nets[0])
        if other_net is None or other_net.is_ground:
            continue
        feeds.append(ref)
    return sorted(feeds)


def is_negligible(component: Optional[Component]) -> bool:
    """True only if the component's eBOM value is known *and* resolves to
    (approximately) 0\u03a9. Unknown values are conservatively treated as
    "could be non-negligible" -- i.e. this returns ``False`` for them."""

    return (
        component is not None
        and component.has_known_value
        and component.value.unit == "ohm"
        and component.value.magnitude <= ZERO_OHM_THRESHOLD
    )
