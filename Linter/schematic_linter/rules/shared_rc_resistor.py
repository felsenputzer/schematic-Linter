"""A resistor shared between two separate RC filter paths can couple two
otherwise-independent filtered nodes together."""

from __future__ import annotations

from collections import defaultdict
from typing import List

from ..config import Severity
from ._common_source import branch_groups, feed_resistors, is_negligible
from .base import Finding, RuleContext

RULE_ID = "shared_rc_resistor"


def _is_source_side_artifact(ctx: RuleContext, match, groups) -> bool:
    """A resistor with a decoupling/filter cap sitting on *both* of its
    terminal nets always produces two mirror-image ``rc_lowpass`` matches
    (mid/source swapped) -- that alone doesn't mean the resistor is really
    shared between two independent measurement branches, only that it has
    caps on each end (a normal, legitimate 2-pole filter).

    It's only a genuine "shared resistor" problem if the *far* side (this
    match's ``mid_net``) is itself a fan-out point (feeding 2+ other
    branches) that's fed non-negligibly from further upstream -- otherwise
    this match is just an artifact of a bypass cap sitting right at a
    low-impedance source, and shouldn't count toward the "shared" total."""

    branch = groups.get(match.details["mid_net"])
    if not branch:
        return False
    feeds = feed_resistors(ctx, match.details["mid_net"], exclude=branch)
    if not feeds:
        return True  # no upstream feed at all -- directly driven, negligible
    return all(is_negligible(ctx.graph.get_component(r)) for r in feeds)


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    matches = ctx.matches_of("rc_lowpass")
    groups = branch_groups(ctx, matches)

    by_resistor = defaultdict(list)
    for m in matches:
        if _is_source_side_artifact(ctx, m, groups):
            continue
        by_resistor[m.details["resistor"]].append(m)

    for resistor, group in sorted(by_resistor.items()):
        if len(group) < 2:
            continue
        capacitors = sorted({m.details["capacitor"] for m in group})
        ground_nets = sorted({m.details["ground_net"] for m in group})
        mid_nets = sorted({m.details["mid_net"] for m in group})
        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=Severity.WARNING,
                title=f"Resistor {resistor} shared across {len(group)} RC filter paths",
                description=(
                    f"Resistor {resistor} forms an RC low-pass with more than one capacitor "
                    f"({', '.join(capacitors)}) on net(s) {', '.join(mid_nets)}, feeding ground "
                    f"net(s) {', '.join(ground_nets)}. Sharing one resistor between separate "
                    "filter paths couples them together and can create interference between "
                    "signals that were meant to be filtered independently."
                ),
                ref_des=[resistor] + capacitors,
                nets=mid_nets + ground_nets,
                pattern_kind="rc_lowpass",
            )
        )
    return findings
