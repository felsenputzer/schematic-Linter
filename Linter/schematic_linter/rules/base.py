"""Shared types for rules.

Each rule module in this package exposes:

- ``RULE_ID: str`` -- a short, stable identifier for the rule.
- ``def evaluate(ctx: RuleContext) -> list[Finding]`` -- inspects the
  recognized patterns (and, if needed, the graph directly) and returns
  zero or more findings.

The registry (``registry.py``) auto-discovers every module in this package
that defines ``evaluate``, so adding/removing a rule is just adding or
deleting a file here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import Severity
from ..graph.model import CircuitGraph
from ..patterns.base import PatternMatch


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    title: str
    description: str
    ref_des: List[str]
    nets: List[str] = field(default_factory=list)
    pattern_kind: Optional[str] = None
    note: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleContext:
    graph: CircuitGraph
    matches: List[PatternMatch]
    has_bom: bool

    def matches_of(self, kind: str) -> List[PatternMatch]:
        return [m for m in self.matches if m.kind == kind]
