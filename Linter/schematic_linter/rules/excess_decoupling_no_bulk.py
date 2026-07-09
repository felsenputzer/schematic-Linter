"""More than a few decoupling caps on one power net without a larger bulk
capacitor is unusual -- may indicate a missing bulk/reservoir cap."""

from __future__ import annotations

from collections import defaultdict
from typing import List

from ..config import (
    BULK_CAP_RATIO,
    MAX_DECOUPLING_CAPS_WITHOUT_BULK,
    NOTE_VALUE_UNKNOWN,
    Severity,
)
from .base import Finding, RuleContext

RULE_ID = "excess_decoupling_no_bulk"


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    by_power_net = defaultdict(list)
    for m in ctx.matches_of("decoupling_cap"):
        by_power_net[m.details["power_net"]].append(m)

    for power_net, group in sorted(by_power_net.items()):
        if len(group) <= MAX_DECOUPLING_CAPS_WITHOUT_BULK:
            continue

        cap_refs = sorted({m.details["capacitor"] for m in group})
        values = []
        any_unknown = False
        for ref in cap_refs:
            component = ctx.graph.get_component(ref)
            if component and component.value_source == "ebom" and component.value is not None:
                values.append(component.value.magnitude)
            else:
                any_unknown = True

        has_bulk = False
        if len(values) >= 2:
            values.sort()
            has_bulk = values[-1] >= BULK_CAP_RATIO * values[-2]
        if has_bulk:
            continue

        note = NOTE_VALUE_UNKNOWN if (any_unknown or not ctx.has_bom) else None
        severity = Severity.INFO

        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=severity,
                title=f"{len(cap_refs)} decoupling caps on '{power_net}' with no clear bulk capacitor",
                description=(
                    f"Power net '{power_net}' has {len(cap_refs)} decoupling capacitors "
                    f"({', '.join(cap_refs)}) but none stands out as a larger bulk/reservoir "
                    "capacitor. This is fine for purely local decoupling, but worth double-"
                    "checking that bulk capacitance exists somewhere on this rail."
                ),
                ref_des=cap_refs,
                nets=[power_net],
                pattern_kind="decoupling_cap",
                note=note,
            )
        )

    return findings
