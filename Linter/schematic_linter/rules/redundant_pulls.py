"""Two or more pull-ups (or pull-downs) on the exact same net are redundant."""

from __future__ import annotations

from collections import defaultdict
from typing import List

from ..config import Severity
from .base import Finding, RuleContext

RULE_ID = "redundant_pulls"


def _check(ctx: RuleContext, kind: str, label: str) -> List[Finding]:
    findings: List[Finding] = []
    by_net = defaultdict(set)
    for m in ctx.matches_of(kind):
        by_net[m.details["signal_net"]].add(m.details["resistor"])

    for net_name, resistors in sorted(by_net.items()):
        if len(resistors) < 2:
            continue
        refs = sorted(resistors)
        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=Severity.WARNING,
                title=f"Redundant {label} resistors on '{net_name}'",
                description=(
                    f"{len(refs)} {label} resistors ({', '.join(refs)}) are all connected to net "
                    f"'{net_name}'. Unless this is an intentional strength adjustment, one of them "
                    "is likely redundant."
                ),
                ref_des=refs,
                nets=[net_name],
                pattern_kind=kind,
            )
        )
    return findings


def evaluate(ctx: RuleContext) -> List[Finding]:
    return _check(ctx, "pull_up", "pull-up") + _check(ctx, "pull_down", "pull-down")
