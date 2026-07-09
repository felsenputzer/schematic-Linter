"""Shared pin-name heuristics for power/ground miswire checks.

Named with a leading underscore (and deliberately defining no ``evaluate``
function) so the rule registry's auto-discovery skips it -- it's a helper
module, not a rule itself.
"""

from __future__ import annotations

import re

POWER_PIN_NAME_RE = re.compile(r"^(VCC|VDD|AVDD|DVDD|VBAT|VPP|V\+)\d*$", re.I)
GROUND_PIN_NAME_RE = re.compile(r"^(GND|VSS|AGND|DGND|V-)\d*$", re.I)
