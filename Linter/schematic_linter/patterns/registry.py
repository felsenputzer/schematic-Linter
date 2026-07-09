"""Auto-discovers and runs every pattern recognizer in this package."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, List

from ..graph.model import CircuitGraph
from .base import PatternMatch

_EXCLUDED_MODULES = {"base", "registry", "__init__"}


def _discover_recognizers() -> List[Callable[[CircuitGraph], List[PatternMatch]]]:
    package = importlib.import_module(__package__)
    recognizers = []
    for _finder, module_name, _is_pkg in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if module_name in _EXCLUDED_MODULES:
            continue
        module = importlib.import_module(f"{__package__}.{module_name}")
        recognize_fn = getattr(module, "recognize", None)
        if callable(recognize_fn):
            recognizers.append(recognize_fn)
    return recognizers


def run_all_recognizers(graph: CircuitGraph) -> List[PatternMatch]:
    matches: List[PatternMatch] = []
    for recognize_fn in _discover_recognizers():
        result = recognize_fn(graph)
        if result:
            matches.extend(result)
    return matches
