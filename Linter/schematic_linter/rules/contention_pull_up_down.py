"""A net with both a pull-up and a pull-down connected to it fights itself
whenever neither side is driving -- a clear structural problem.

One important exception: a resistive voltage divider (one resistor to a
supply, one to ground, tap read by something) is *topologically*
indistinguishable from a pull-up/pull-down pair on the same net -- it's the
same two-resistor shape. That's a completely normal, intentional pattern
(e.g. a resistive bias network feeding an ADC input), not a bug. So this
rule only flags contention when it *isn't* fully explained by a single
clean divider pair (exactly one pull-up resistor and one pull-down
resistor on the net, matching exactly the two resistors of a recognized
voltage divider on that same net). Anything messier than that -- e.g. an
extra pull-up on top of a divider, or pull-up/pull-down resistors with no
divider relationship between them at all -- is still flagged.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

from ..config import Severity
from .base import Finding, RuleContext

RULE_ID = "contention_pull_up_down"


def _is_clean_divider_pair(ctx: RuleContext, net_name: str, up_refs: set, down_refs: set) -> bool:
    if len(up_refs) != 1 or len(down_refs) != 1:
        return False
    pair = up_refs | down_refs
    for divider in ctx.matches_of("voltage_divider"):
        if divider.details["tap_net"] != net_name:
            continue
        if {divider.details["top_resistor"], divider.details["bottom_resistor"]} == pair:
            return True
    return False


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    pull_ups_by_net = defaultdict(list)
    for m in ctx.matches_of("pull_up"):
        pull_ups_by_net[m.details["signal_net"]].append(m)

    pull_downs_by_net = defaultdict(list)
    for m in ctx.matches_of("pull_down"):
        pull_downs_by_net[m.details["signal_net"]].append(m)

    contended_nets = set(pull_ups_by_net) & set(pull_downs_by_net)
    for net_name in sorted(contended_nets):
        ups = pull_ups_by_net[net_name]
        downs = pull_downs_by_net[net_name]
        up_refs = {m.details["resistor"] for m in ups}
        down_refs = {m.details["resistor"] for m in downs}

        if _is_clean_divider_pair(ctx, net_name, up_refs, down_refs):
            continue

        up_refs_sorted = sorted(up_refs)
        down_refs_sorted = sorted(down_refs)
        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=Severity.ERROR,
                title=f"Pull-up/pull-down contention on '{net_name}'",
                description=(
                    f"Net '{net_name}' has both pull-up resistor(s) {', '.join(up_refs_sorted)} and "
                    f"pull-down resistor(s) {', '.join(down_refs_sorted)}. When nothing else on the "
                    "net is actively driving it, these fight each other and hold the net at an "
                    "indeterminate voltage between rails."
                ),
                ref_des=up_refs_sorted + down_refs_sorted,
                nets=[net_name],
                pattern_kind="pull_up+pull_down",
            )
        )

    return findings
