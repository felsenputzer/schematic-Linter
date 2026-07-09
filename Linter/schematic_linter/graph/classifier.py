"""Classifies components into a small set of functional kinds.

Classification precedence (first match wins):

1. Reference-designator prefix (the IPC-ish convention engineers already
   rely on: ``R1`` is a resistor, ``C4`` a capacitor, ``U1`` an IC, ...).
   This is the ground truth in practice and is robust across libraries.
2. Netlist component-type keyword (e.g. ``"RESISTOR"``, ``"CAPA"``,
   ``"74XX595"``, ``"PIC18F2XK22_QFN28"``).
3. eBOM description keyword (e.g. an "IR LED" ref-des'd oddly as ``BLK0002``
   still gets recognized as a diode from its description).
4. ``OTHER`` if nothing matched.

The table-driven design means adding support for a new part family/prefix
is a one-line change.
"""

from __future__ import annotations

import re
from typing import Optional

from .model import ComponentKind

# Longer prefixes must be listed so they're checked before shorter ones
# that would otherwise shadow them (e.g. "TP" before "T").
_REF_DES_PREFIX_KIND = [
    ("TP", ComponentKind.TESTPOINT),
    ("FL", ComponentKind.INDUCTOR),
    ("CN", ComponentKind.CONNECTOR),
    ("RN", ComponentKind.RESISTOR),
    ("CR", ComponentKind.DIODE),
    ("SW", ComponentKind.OTHER),
    ("IC", ComponentKind.IC),
    ("R", ComponentKind.RESISTOR),
    ("C", ComponentKind.CAPACITOR),
    ("L", ComponentKind.INDUCTOR),
    ("D", ComponentKind.DIODE),
    ("Q", ComponentKind.TRANSISTOR),
    ("U", ComponentKind.IC),
    ("Y", ComponentKind.CRYSTAL),
    ("X", ComponentKind.CRYSTAL),
    ("J", ComponentKind.CONNECTOR),
    ("P", ComponentKind.CONNECTOR),
]
_REF_DES_PREFIX_KIND.sort(key=lambda pair: -len(pair[0]))

_LEADING_DIGITS_RE = re.compile(r"^\d*")
_LEADING_ALPHA_RE = re.compile(r"^[A-Za-z]+")

_COMP_TYPE_KEYWORDS = [
    (re.compile(r"RESISTOR", re.I), ComponentKind.RESISTOR),
    (re.compile(r"CAPA|DECOUPLING|MLCC", re.I), ComponentKind.CAPACITOR),
    (re.compile(r"CHOKE|INDUC|FILTER_EMC", re.I), ComponentKind.INDUCTOR),
    (re.compile(r"DIOD|SCHOTTKY|TRANSIL|\bLED\b", re.I), ComponentKind.DIODE),
    (re.compile(r"TESTPOINT", re.I), ComponentKind.TESTPOINT),
    (re.compile(r"QUARTZ|CRYSTAL|\bXTAL\b", re.I), ComponentKind.CRYSTAL),
    (re.compile(r"CONNECTOR", re.I), ComponentKind.CONNECTOR),
    (re.compile(r"NPN|PNP|TRANSISTOR", re.I), ComponentKind.TRANSISTOR),
    (re.compile(r"AMPLIFIER|PIC\d|\d{2,3}XX\d+|\bIC\b|MICRO", re.I), ComponentKind.IC),
]

_DESCRIPTION_KEYWORDS = [
    (re.compile(r"\bLED\b|DIOD", re.I), ComponentKind.DIODE),
    (re.compile(r"\bRES\b|RESISTOR", re.I), ComponentKind.RESISTOR),
    (re.compile(r"\bCAP\b|CAPACITOR|CER\b", re.I), ComponentKind.CAPACITOR),
    (re.compile(r"INDUC|CHOKE|\bCOIL\b", re.I), ComponentKind.INDUCTOR),
    (re.compile(r"QTZ|QUARTZ|CRYSTAL", re.I), ComponentKind.CRYSTAL),
    (re.compile(r"\bIC\b|AMP\b|MICRO", re.I), ComponentKind.IC),
    (re.compile(r"TRANSISTOR|\bTR-", re.I), ComponentKind.TRANSISTOR),
    (re.compile(r"CONNECTOR|\bJST\b|\bPLUG\b", re.I), ComponentKind.CONNECTOR),
]


def _classify_by_ref_des(ref_des: str) -> Optional[ComponentKind]:
    stripped = _LEADING_DIGITS_RE.sub("", ref_des, count=1)
    alpha_match = _LEADING_ALPHA_RE.match(stripped)
    if not alpha_match:
        return None
    prefix = alpha_match.group(0).upper()
    for candidate_prefix, kind in _REF_DES_PREFIX_KIND:
        if prefix.startswith(candidate_prefix):
            return kind
    return None


def _classify_by_keywords(text: str, table) -> Optional[ComponentKind]:
    for pattern, kind in table:
        if pattern.search(text):
            return kind
    return None


def classify_component(ref_des: str, comp_types: list[str], bom_description: Optional[str] = None) -> ComponentKind:
    """Determine the functional kind of a component.

    ``comp_types`` may contain more than one raw netlist type string when a
    multi-gate part (e.g. a dual op-amp) reports a different type per pin
    group; any of them matching is enough.
    """

    by_ref = _classify_by_ref_des(ref_des)
    if by_ref is not None:
        return by_ref

    for comp_type in comp_types:
        by_type = _classify_by_keywords(comp_type, _COMP_TYPE_KEYWORDS)
        if by_type is not None:
            return by_type

    if bom_description:
        by_desc = _classify_by_keywords(bom_description, _DESCRIPTION_KEYWORDS)
        if by_desc is not None:
            return by_desc

    return ComponentKind.OTHER
