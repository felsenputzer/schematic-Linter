"""Parses eBOM component values written in common engineering shorthand.

Handles things like ``"10k"``, ``"4.7uF"``, ``"0R"``, ``"5.6K"``, ``"1nF"``,
``"51uH"``, ``"20MHz"`` as well as the European embedded-decimal shorthand
``"4k7"`` / ``"2R2"``.

This module is intentionally decoupled from the graph/component model: it
takes a lightweight ``ValueKind`` hint (used only to pick a sensible default
unit when the raw string has a multiplier but no unit letter, e.g. plain
``"200"`` on a resistor) rather than depending on the graph package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ValueKind(str, Enum):
    """Hint about what physical quantity a value is expected to represent."""

    RESISTANCE = "resistance"
    CAPACITANCE = "capacitance"
    INDUCTANCE = "inductance"
    FREQUENCY = "frequency"
    UNKNOWN = "unknown"


_DEFAULT_UNIT_FOR_KIND = {
    ValueKind.RESISTANCE: "ohm",
    ValueKind.CAPACITANCE: "F",
    ValueKind.INDUCTANCE: "H",
    ValueKind.FREQUENCY: "Hz",
    ValueKind.UNKNOWN: "ohm",
}

# Order matters within each alternation: longer/more-specific tokens first.
_MULTIPLIERS = {
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "\u00b5": 1e-6,  # micro sign
    "m": 1e-3,
    "": 1.0,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
}

_UNIT_CANONICAL = {
    "hz": "Hz",
    "ohm": "ohm",
    "ohms": "ohm",
    "\u03a9": "ohm",
    "r": "ohm",
    "f": "F",
    "h": "H",
}

_STANDARD_RE = re.compile(
    r"""^\s*
    (?P<num>\d+(?:\.\d+)?)
    \s*
    (?P<mult>[pnu\u00b5mkKMG]?)
    \s*
    (?P<unit>Hz|ohms|ohm|\u03a9|R|F|H)?
    \s*$""",
    re.VERBOSE,
)

# European shorthand where the multiplier/unit letter stands in for the
# decimal point, e.g. "4k7" == 4.7k, "2R2" == 2.2 ohm, "0R" == 0 ohm.
_SHORTHAND_RE = re.compile(
    r"""^\s*
    (?P<int>\d+)
    (?P<mult>[pnu\u00b5mkKMGR])
    (?P<frac>\d+)?
    \s*$""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class ParsedValue:
    """A normalized component value."""

    raw: str
    magnitude: float  # in base SI units (ohm, F, H, Hz)
    unit: str  # "ohm" | "F" | "H" | "Hz"
    display: str  # human-friendly normalized string, e.g. "5.6 kOhm"

    @property
    def is_zero(self) -> bool:
        return self.magnitude == 0.0


class ValueParseError(Exception):
    """Raised when a raw value string cannot be interpreted at all."""


_PREFIX_FOR_MAGNITUDE = [
    (1e9, "G"),
    (1e6, "M"),
    (1e3, "k"),
    (1.0, ""),
    (1e-3, "m"),
    (1e-6, "\u00b5"),
    (1e-9, "n"),
    (1e-12, "p"),
]


def _format_display(magnitude: float, unit: str) -> str:
    unit_label = "Ohm" if unit == "ohm" else unit
    if magnitude == 0:
        return f"0 {unit_label}"
    for threshold, prefix in _PREFIX_FOR_MAGNITUDE:
        if abs(magnitude) >= threshold:
            scaled = magnitude / threshold
            text = f"{scaled:g}"
            return f"{text} {prefix}{unit_label}"
    return f"{magnitude:g} {unit_label}"


def parse_value(raw: str, kind: ValueKind = ValueKind.UNKNOWN) -> Optional[ParsedValue]:
    """Parse a raw eBOM value string into a ``ParsedValue``.

    Returns ``None`` (rather than raising) when the string is empty/blank,
    since a missing value should be treated as "value unknown", not an
    error -- callers typically want to fall back gracefully.

    Raises ``ValueParseError`` if the string is non-empty but not
    recognizable, so genuinely malformed BOM data is not silently ignored.
    """

    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    match = _STANDARD_RE.match(text)
    if match:
        num = float(match.group("num"))
        mult_char = match.group("mult") or ""
        unit_raw = match.group("unit")
        magnitude = num * _MULTIPLIERS.get(mult_char, 1.0)
        unit = _UNIT_CANONICAL.get(unit_raw.lower(), None) if unit_raw else None
        if unit is None:
            unit = _DEFAULT_UNIT_FOR_KIND.get(kind, "ohm")
        display = _format_display(magnitude, unit)
        return ParsedValue(raw=raw, magnitude=magnitude, unit=unit, display=display)

    match = _SHORTHAND_RE.match(text)
    if match:
        int_part = match.group("int")
        mult_char = match.group("mult")
        frac_part = match.group("frac") or ""
        combined = f"{int_part}.{frac_part}" if frac_part else int_part
        num = float(combined)
        if mult_char == "R":
            magnitude = num
            unit = "ohm"
        else:
            magnitude = num * _MULTIPLIERS.get(mult_char, 1.0)
            unit = _DEFAULT_UNIT_FOR_KIND.get(kind, "ohm")
        display = _format_display(magnitude, unit)
        return ParsedValue(raw=raw, magnitude=magnitude, unit=unit, display=display)

    raise ValueParseError(f"Could not parse component value {raw!r}")
