"""Shared types for pattern recognizers.

Each recognizer module in this package exposes:

- ``PATTERN_KIND: str`` -- a short, stable identifier for the pattern.
- ``def recognize(graph: CircuitGraph) -> list[PatternMatch]`` -- inspects
  the graph and returns every instance of the pattern found.

The registry (``registry.py``) auto-discovers every module in this package
that defines ``recognize``, so adding a new pattern is just adding a new
file here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PatternMatch:
    kind: str
    components: List[str]
    nets: List[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)

    def involves(self, ref_des: str) -> bool:
        return ref_des in self.components
