"""Auto-discovers and runs every rule in this package."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, List

from .base import Finding, RuleContext

_EXCLUDED_MODULES = {"base", "registry", "__init__"}


def _discover_rules() -> List[Callable[[RuleContext], List[Finding]]]:
    package = importlib.import_module(__package__)
    rules = []
    for _finder, module_name, _is_pkg in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if module_name in _EXCLUDED_MODULES:
            continue
        module = importlib.import_module(f"{__package__}.{module_name}")
        evaluate_fn = getattr(module, "evaluate", None)
        if callable(evaluate_fn):
            rules.append(evaluate_fn)
    return rules


def run_all_rules(ctx: RuleContext) -> List[Finding]:
    findings: List[Finding] = []
    for evaluate_fn in _discover_rules():
        result = evaluate_fn(ctx)
        if result:
            findings.extend(result)
    return findings
