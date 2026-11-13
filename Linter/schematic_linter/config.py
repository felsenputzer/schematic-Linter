"""Central, easily-tunable constants used across the linter.

Keeping these in one place makes it easy to retune thresholds (e.g. "how
many decoupling caps counts as too many") without hunting through rule
files.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterator, Mapping, Optional, Tuple, Union


class Severity(str, Enum):
    """Finding severity, ordered from most to least urgent."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"error": 0, "warning": 1, "info": 2}[self.value]

    @property
    def label(self) -> str:
        return self.value.upper()


# --- Rule thresholds -------------------------------------------------------

# More than this many decoupling caps on one power net, with no bulk cap
# present, is flagged as unusual (Info).
MAX_DECOUPLING_CAPS_WITHOUT_BULK = 4

# A capacitor counts as a "bulk" cap relative to the decoupling caps on the
# same net if its capacitance is at least this many times larger than the
# largest decoupling cap on that net.
BULK_CAP_RATIO = 10.0

# eBOM value magnitude (in ohms) at or below which a pull resistor is
# considered a "0 ohm jumper" rather than a real pull resistor.
ZERO_OHM_THRESHOLD = 0.5

NOTE_VALUE_UNKNOWN = "value unknown \u2014 check manually"

# Minimum number of instances of the identical part (same netlist comp-type)
# required before comparing their pin-to-net wiring against each other. Below
# this, "majority" is meaningless (e.g. 2 instances is always a 50/50 tie).
SIBLING_GROUP_MIN_SIZE = 3

# Minimum number of pin names shared by every member of a sibling group
# before the comparison is considered meaningful. This excludes generic
# 2-pin passives (resistors, capacitors, ...) whose pin names (e.g. "A"/"B")
# don't carry a part-specific function that should stay consistent across
# unrelated instances.
SIBLING_MIN_COMMON_PIN_NAMES = 3

# How many inline 2-pin passive hops to resolve through when canonicalizing
# a net for sibling pin comparison (e.g. a series-termination resistor
# between a driver pin and the "real" bussed net it logically belongs to).
SIBLING_NET_RESOLVE_MAX_HOPS = 2


# --- User-tunable thresholds -------------------------------------------
# The subset of the constants above that the GUI (and ``override()``)
# exposes for tuning. Rules must read these as ``config.NAME`` at call
# time (not ``from ..config import NAME``) so an override takes effect.


@dataclass(frozen=True)
class Threshold:
    key: str  # module-level constant name in this file
    label: str
    help: str
    kind: type  # int or float
    minimum: float
    maximum: float
    used_by: Tuple[str, ...]  # RULE_IDs that read it

    @property
    def default(self) -> Union[int, float]:
        return _DEFAULTS[self.key]


TUNABLE_THRESHOLDS: Tuple[Threshold, ...] = (
    Threshold(
        "MAX_DECOUPLING_CAPS_WITHOUT_BULK",
        "Max. decoupling caps per rail without a bulk cap",
        "More decoupling caps than this on one power net, with no bulk cap, is reported.",
        int, 1, 100, ("excess_decoupling_no_bulk",),
    ),
    Threshold(
        "BULK_CAP_RATIO",
        "Bulk cap size ratio",
        "A cap counts as 'bulk' if it is at least this many times larger than the largest decoupling cap.",
        float, 1.0, 10000.0, ("excess_decoupling_no_bulk",),
    ),
    Threshold(
        "ZERO_OHM_THRESHOLD",
        "0 \u03a9 jumper threshold [\u03a9]",
        "Resistors at or below this value are treated as 0 \u03a9 jumpers rather than real resistors.",
        float, 0.0, 100.0, ("zero_ohm_pull_review", "shared_rc_resistor", "shared_source_resistor"),
    ),
    Threshold(
        "SIBLING_GROUP_MIN_SIZE",
        "Min. repeated instances to compare",
        "A part must repeat at least this many times before its instances' wiring is compared.",
        int, 3, 1000, ("sibling_pin_mismatch",),
    ),
    Threshold(
        "SIBLING_MIN_COMMON_PIN_NAMES",
        "Min. common pin names",
        "Repeated parts must share at least this many pin names to be compared (excludes plain passives).",
        int, 1, 1000, ("sibling_pin_mismatch",),
    ),
    Threshold(
        "SIBLING_NET_RESOLVE_MAX_HOPS",
        "Series-resistor hops to look through",
        "How many inline series resistors/inductors to see through when comparing nets of repeated parts.",
        int, 0, 10, ("sibling_pin_mismatch",),
    ),
)

_DEFAULTS: Dict[str, Union[int, float]] = {t.key: globals()[t.key] for t in TUNABLE_THRESHOLDS}
_BY_KEY: Dict[str, Threshold] = {t.key: t for t in TUNABLE_THRESHOLDS}


def validate_thresholds(values: Mapping[str, object]) -> Dict[str, Union[int, float]]:
    """Returns ``values`` cast to each threshold's type; raises ``ValueError``
    naming the offending threshold on an unknown key, a non-number, or an
    out-of-range value."""

    clean: Dict[str, Union[int, float]] = {}
    for key, raw in values.items():
        spec = _BY_KEY.get(key)
        if spec is None:
            raise ValueError(f"Unknown threshold '{key}'")
        try:
            number = float(raw)
            if spec.kind is int:
                if number != int(number):
                    raise ValueError
                number = int(number)
        except (TypeError, ValueError):
            kind = "a whole number" if spec.kind is int else "a number"
            raise ValueError(f"'{spec.label}' must be {kind} (got {raw!r})") from None
        if not spec.minimum <= number <= spec.maximum:
            raise ValueError(f"'{spec.label}' must be between {spec.minimum:g} and {spec.maximum:g} (got {number:g})")
        clean[key] = number
    return clean


@contextmanager
def override(values: Optional[Mapping[str, object]]) -> Iterator[None]:
    """Temporarily sets tunable thresholds for the duration of a ``with``
    block (one analysis run), restoring the previous values afterwards."""

    clean = validate_thresholds(values or {})
    module_globals = globals()
    previous = {key: module_globals[key] for key in clean}
    module_globals.update(clean)
    try:
        yield
    finally:
        module_globals.update(previous)


# --- PDF crop sizing ---------------------------------------------------
# Margin (in PDF points) added around a reference designator's text hit
# when cropping a snippet out of the schematic PDF. Larger components need
# more surrounding context to be useful to the engineer.

CROP_MARGIN_SMALL = 90.0   # discrete passives: R, C, L, D, TP
CROP_MARGIN_MEDIUM = 180.0  # transistors, crystals, connectors
CROP_MARGIN_LARGE = 320.0  # ICs

# If the computed crop would exceed this fraction of the page's area, fall
# back to rendering the full page with the match highlighted instead of an
# oversized/awkward crop.
CROP_FULL_PAGE_AREA_FRACTION = 0.6

# Rendering resolution for cropped snippets.
CROP_DPI = 200

# --- Output layout -------------------------------------------------------

REPORTS_DIRNAME = "Reports"
GRAPH_FILENAME = "graph.json"
REPORT_FILENAME = "report.html"
