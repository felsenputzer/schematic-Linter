"""A designator whose prefix disagrees with what the part actually is
(per its library symbol or eBOM description) -- e.g. a crystal named
``X1`` when ``X`` is reserved for special test points. Besides confusing
people, it can make other checks misjudge the part, so the classifier's
reasoning is surfaced here."""

from __future__ import annotations

from typing import List

from ..config import Severity
from .base import Finding, RuleContext

RULE_ID = "designator_kind_mismatch"
RULE_NAME = "Designator doesn't match part type"
RULE_DESCRIPTION = (
    "The ref-des prefix disagrees with the part's library symbol or eBOM description "
    "(e.g. a crystal named like a test point)."
)


def evaluate(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []

    for ref_des, component in sorted(ctx.graph.components.items()):
        if not component.classification_notes:
            continue
        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity=Severity.INFO,
                title=f"{ref_des}: designator doesn't match the part type",
                description=(
                    f"{ref_des} ({', '.join(component.comp_types) or 'no symbol type'}): "
                    + "; ".join(component.classification_notes)
                    + f". Treated as {component.kind.value} by the other checks. "
                    "Check the designator against the company prefix convention."
                ),
                ref_des=[ref_des],
                details={"kind": component.kind.value, "kind_source": component.kind_source},
            )
        )

    return findings
