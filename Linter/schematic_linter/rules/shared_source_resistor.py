"""A resistor that feeds a node shared by two or more independently-filtered
RC branches (e.g. two redundant measurement dividers fed from the same
op-amp output) injects its own value into both branches' effective source
impedance. Current drawn by either branch then develops a voltage drop
across that shared resistor which is visible to the other branch, coupling
two signals that were meant to be measured independently.

A resistor of (approximately) 0\u03a9 in that spot is harmless -- it isn't
really adding any impedance -- so it's deliberately not flagged."""

from __future__ import annotations

from typing import List

from ..config import NOTE_VALUE_UNKNOWN, Severity
from ._common_source import branch_groups, feed_resistors, is_negligible
from .base import Finding, RuleContext

RULE_ID = "shared_source_resistor"


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    matches = ctx.matches_of("rc_lowpass")
    groups = branch_groups(ctx, matches)

    seen_feed_resistors = set()

    for source_net, branch_resistors in sorted(groups.items()):
        group_matches = [
            m
            for m in matches
            if m.details["source_net"] == source_net and m.details["resistor"] in branch_resistors
        ]
        capacitors = sorted({m.details["capacitor"] for m in group_matches})
        mid_nets = sorted({m.details["mid_net"] for m in group_matches})

        for feed_resistor in feed_resistors(ctx, source_net, exclude=branch_resistors):
            if feed_resistor in seen_feed_resistors:
                continue

            component = ctx.graph.get_component(feed_resistor)
            if is_negligible(component):
                continue
            seen_feed_resistors.add(feed_resistor)

            ref_des = [feed_resistor] + branch_resistors + capacitors
            nets = [source_net] + mid_nets

            if component is not None and component.has_known_value:
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        severity=Severity.WARNING,
                        title=(
                            f"Resistor {feed_resistor} is a common source impedance for "
                            f"{len(branch_resistors)} independent RC branches"
                        ),
                        description=(
                            f"{feed_resistor} ({component.value.display}) feeds net '{source_net}', "
                            f"which fans out through {', '.join(branch_resistors)} into separately "
                            f"filtered branches ({', '.join(mid_nets)}, via {', '.join(capacitors)}). "
                            f"Current drawn by either branch develops a voltage drop across "
                            f"{feed_resistor} that's visible to the other branch, coupling two "
                            "measurements that were meant to be independent. If this is intentional "
                            "(e.g. a deliberate summing/bias node), please confirm; otherwise each "
                            "branch should be fed directly from the low-impedance source."
                        ),
                        ref_des=ref_des,
                        nets=nets,
                        pattern_kind="rc_lowpass",
                    )
                )
            else:
                findings.append(
                    Finding(
                        rule_id=RULE_ID,
                        severity=Severity.INFO,
                        title=f"Resistor {feed_resistor} feeding shared node '{source_net}' has an unknown value",
                        description=(
                            f"{feed_resistor} feeds net '{source_net}', which fans out through "
                            f"{', '.join(branch_resistors)} into separately filtered branches "
                            f"({', '.join(mid_nets)}). Unless {feed_resistor} is (close to) 0\u03a9, "
                            "current through one branch will develop a voltage drop visible to the "
                            f"other -- {NOTE_VALUE_UNKNOWN}."
                        ),
                        ref_des=ref_des,
                        nets=nets,
                        pattern_kind="rc_lowpass",
                        note=NOTE_VALUE_UNKNOWN,
                    )
                )

    return findings
