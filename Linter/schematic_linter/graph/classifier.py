"""Classifies components into a small set of functional kinds.

Three independent pieces of evidence are available for every part:

1. **Reference-designator prefix** -- the company convention engineers
   rely on (``R1`` resistor, ``C4`` capacitor, ``Y1`` crystal/oscillator,
   ``X1`` special test point, ...). Typed by hand, so occasionally wrong.
2. **Netlist component type** -- the library symbol name (``"RESISTOR"``,
   ``"QUARTZ_NX2016AA"``, ``"TESTPOINT"``). Comes from the library, so when
   it clearly names a part family it is the most trustworthy source.
3. **eBOM description** -- e.g. ``"QTZ 20MHz 10ppm 5pF SMD"`` or
   ``"IR LED 850nm ..."``. Useful for parts with an odd ref-des
   (``BLK0002``), but weaker: free text, and absent without an eBOM.

Resolution:

- The ref-des prefix decides, *unless* the library symbol clearly names a
  different family -- then the symbol wins. A disagreement with the eBOM
  description alone is noted but doesn't override the prefix.
- With no recognizable prefix, symbol, then description is used.
- Crystals are then split into passive **crystals** and active
  **oscillators** using the netlist context: an oscillator keyword in the
  symbol/description, a pin on a POWER net, or supply/output pin names
  (``VCC``, ``OUT``, ``EN``, ...). Only passive crystals need load caps;
  oscillators need decoupling like an IC.
- A "crystal"/"oscillator" with fewer than two pins can't be one, so it
  drops to ``OTHER``.

Every disagreement is recorded in ``Classification.notes`` so the
``designator_kind_mismatch`` rule can report it -- a mismatched designator
is worth fixing in the schematic, not just working around here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from .model import ComponentKind

SOURCE_REF_DES = "ref_des"
SOURCE_COMP_TYPE = "comp_type"
SOURCE_BOM_DESCRIPTION = "bom_description"
SOURCE_NONE = "none"

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
    # Company convention: Y = crystals *and* oscillators (split below by
    # netlist context), X = special test points.
    ("Y", ComponentKind.CRYSTAL),
    ("X", ComponentKind.TESTPOINT),
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
    (re.compile(r"TESTPOINT|TEST_POINT", re.I), ComponentKind.TESTPOINT),
    (re.compile(r"OSCILLATOR|QUARTZ|CRYSTAL|\bXTAL\b|(?:^|_)(?:T|VC|OC)?XO(?:_|$)", re.I), ComponentKind.CRYSTAL),
    (re.compile(r"CONNECTOR", re.I), ComponentKind.CONNECTOR),
    (re.compile(r"NPN|PNP|TRANSISTOR", re.I), ComponentKind.TRANSISTOR),
    (re.compile(r"AMPLIFIER|PIC\d|\d{2,3}XX\d+|\bIC\b|MICRO", re.I), ComponentKind.IC),
]

_DESCRIPTION_KEYWORDS = [
    (re.compile(r"\bLED\b|DIOD", re.I), ComponentKind.DIODE),
    (re.compile(r"\bRES\b|RESISTOR", re.I), ComponentKind.RESISTOR),
    (re.compile(r"\bCAP\b|CAPACITOR|CER\b", re.I), ComponentKind.CAPACITOR),
    (re.compile(r"INDUC|CHOKE|\bCOIL\b", re.I), ComponentKind.INDUCTOR),
    (re.compile(r"QTZ|QUARTZ|CRYSTAL|\bXTAL\b|\bOSC|\b(?:T|VC|OC)?XO\b", re.I), ComponentKind.CRYSTAL),
    (re.compile(r"TEST ?POINT|\bTP\b", re.I), ComponentKind.TESTPOINT),
    (re.compile(r"\bIC\b|AMP\b|MICRO", re.I), ComponentKind.IC),
    (re.compile(r"TRANSISTOR|\bTR-", re.I), ComponentKind.TRANSISTOR),
    (re.compile(r"CONNECTOR|\bJST\b|\bPLUG\b", re.I), ComponentKind.CONNECTOR),
]

# Evidence that a CRYSTAL-family part is an active oscillator module.
_OSCILLATOR_TEXT_RE = re.compile(r"OSC|\b(?:T|VC|OC)?XO\b|(?:^|_)(?:T|VC|OC)?XO(?:_|$)|\bMEMS\b", re.I)
_OSCILLATOR_PIN_NAMES = {"VCC", "VDD", "VS", "OUT", "OUTPUT", "CLK", "CLKOUT", "EN", "OE", "ST", "STBY", "TRI"}


@dataclass(frozen=True)
class Classification:
    kind: ComponentKind
    source: str = SOURCE_NONE
    notes: Tuple[str, ...] = ()


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


def _family(kind: Optional[ComponentKind]) -> Optional[ComponentKind]:
    """Crystal and oscillator share a designator; treat them as one family
    when comparing evidence."""

    return ComponentKind.CRYSTAL if kind == ComponentKind.OSCILLATOR else kind


def _label(kind: ComponentKind) -> str:
    return kind.value.lower().replace("_", " ")


def _is_oscillator(
    comp_types: Iterable[str],
    bom_description: Optional[str],
    pin_names: Iterable[str],
    on_power_net: bool,
) -> bool:
    if any(_OSCILLATOR_TEXT_RE.search(t) for t in comp_types):
        return True
    if bom_description and _OSCILLATOR_TEXT_RE.search(bom_description):
        return True
    if on_power_net:
        return True
    return any(name.strip().upper() in _OSCILLATOR_PIN_NAMES for name in pin_names)


def classify(
    ref_des: str,
    comp_types: list[str],
    bom_description: Optional[str] = None,
    pin_names: Optional[Iterable[str]] = None,
    on_power_net: bool = False,
) -> Classification:
    """Determine a component's functional kind from all available evidence.

    ``comp_types`` may contain more than one raw netlist type string when a
    multi-gate part (e.g. a dual op-amp) reports a different type per pin
    group; the first one that matches a family counts.
    ``pin_names`` are all of the part's pin names (connected or not) and
    ``on_power_net`` whether any pin sits on a POWER net -- both only used
    to tell crystals from oscillators and to sanity-check pin counts
    (``pin_names=None`` = unknown, skips the pin-count check).
    """

    pin_count_known = pin_names is not None
    pin_names = list(pin_names or ())
    notes = []

    by_ref = _classify_by_ref_des(ref_des)
    by_type, matched_type = None, None
    for comp_type in comp_types:
        by_type = _classify_by_keywords(comp_type, _COMP_TYPE_KEYWORDS)
        if by_type is not None:
            matched_type = comp_type
            break
    by_desc = _classify_by_keywords(bom_description, _DESCRIPTION_KEYWORDS) if bom_description else None

    if by_ref is not None:
        kind, source = by_ref, SOURCE_REF_DES
        if by_type is not None and _family(by_type) != _family(by_ref):
            notes.append(
                f"designator prefix suggests {_label(by_ref)}, but library symbol '{matched_type}' is a "
                f"{_label(by_type)}; using {_label(by_type)}"
            )
            kind, source = by_type, SOURCE_COMP_TYPE
        elif by_type is None and by_desc is not None and _family(by_desc) != _family(by_ref):
            notes.append(
                f"designator prefix suggests {_label(by_ref)}, but eBOM description '{bom_description}' "
                f"reads like a {_label(by_desc)}; kept {_label(by_ref)}"
            )
    elif by_type is not None:
        kind, source = by_type, SOURCE_COMP_TYPE
    elif by_desc is not None:
        kind, source = by_desc, SOURCE_BOM_DESCRIPTION
    else:
        return Classification(ComponentKind.OTHER, SOURCE_NONE, ())

    if kind == ComponentKind.CRYSTAL:
        if pin_count_known and len(pin_names) < 2:
            notes.append(f"classified as crystal/oscillator by {source}, but it has only {len(pin_names)} pin(s)")
            kind = ComponentKind.OTHER
        elif _is_oscillator(comp_types, bom_description, pin_names, on_power_net):
            kind = ComponentKind.OSCILLATOR

    return Classification(kind, source, tuple(notes))


def classify_component(ref_des: str, comp_types: list[str], bom_description: Optional[str] = None) -> ComponentKind:
    """Backwards-compatible shortcut: just the kind, without pin context."""

    return classify(ref_des, comp_types, bom_description).kind
