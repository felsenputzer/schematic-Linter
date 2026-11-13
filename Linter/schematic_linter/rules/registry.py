"""Auto-discovers and runs every rule in this package."""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable, Collection, List, Optional

from .base import Finding, RuleContext

_EXCLUDED_MODULES = {"base", "registry", "__init__"}


@dataclass(frozen=True)
class RuleInfo:
    """A discovered rule plus the human-readable metadata the GUI/CLI show."""

    rule_id: str
    name: str
    description: str
    requires_bom: bool
    evaluate: Callable[[RuleContext], List[Finding]]


def available_rules() -> List[RuleInfo]:
    """Every rule module in this package that defines ``evaluate``, sorted
    by module name. Private helper modules (``_*.py``) define no
    ``evaluate`` and are skipped."""

    package = importlib.import_module(__package__)
    rules = []
    for _finder, module_name, _is_pkg in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if module_name in _EXCLUDED_MODULES:
            continue
        module = importlib.import_module(f"{__package__}.{module_name}")
        evaluate_fn = getattr(module, "evaluate", None)
        if not callable(evaluate_fn):
            continue
        rule_id = getattr(module, "RULE_ID", module_name)
        rules.append(
            RuleInfo(
                rule_id=rule_id,
                name=getattr(module, "RULE_NAME", rule_id.replace("_", " ").capitalize()),
                description=getattr(module, "RULE_DESCRIPTION", ""),
                requires_bom=bool(getattr(module, "RULE_REQUIRES_BOM", False)),
                evaluate=evaluate_fn,
            )
        )
    return rules


def run_all_rules(ctx: RuleContext, enabled: Optional[Collection[str]] = None) -> List[Finding]:
    """Runs every rule (or only those whose ``rule_id`` is in ``enabled``)."""

    findings: List[Finding] = []
    for rule in available_rules():
        if enabled is not None and rule.rule_id not in enabled:
            continue
        result = rule.evaluate(ctx)
        if result:
            findings.extend(result)
    return findings
