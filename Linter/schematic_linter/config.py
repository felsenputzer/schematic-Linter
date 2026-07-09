"""Central, easily-tunable constants used across the linter.

Keeping these in one place makes it easy to retune thresholds (e.g. "how
many decoupling caps counts as too many") without hunting through rule
files.
"""

from __future__ import annotations

from enum import Enum


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
