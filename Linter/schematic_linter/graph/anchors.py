"""Identifies power and ground ("anchor") nets.

The Zuken exporter already tags each pin record with ``NET_TYPE`` of
``GROUND``, ``POWER``, or blank, and that tag is treated as fully
authoritative -- deliberately *no* name-based guessing (e.g. "starts with
V" or "contains RAW") is layered on top.

An earlier version of this module added a conservative-looking name-based
fallback (flagging nets named like ``VCC``/``RAW_*``/etc. as power when
untagged) to catch a couple of untagged supply-ish net names. In practice
it backfired: nets ``RAW_1``/``RAW_2`` in the bundled sample are *not*
power rails -- they're feedback/base-drive nodes between an op-amp output
and a transistor base that simply happen to be named "RAW_n" -- and the
exporter correctly leaves them untagged. Guessing from the name promoted
them to "power", which in turn made the pull-up pattern misfire on two
resistors that are actually just links in an op-amp-to-transistor drive
path (see ``081708R12``/``08R09``). The netlist's own tagging is the only
reliable signal here, so the heuristic was removed rather than patched.
"""

from __future__ import annotations

from typing import Iterable, Tuple

from ..parsers.netlist_parser import PinRecord


def anchor_flags_for_net(net_name: str, records: Iterable[PinRecord]) -> Tuple[bool, bool]:
    """Returns ``(is_power, is_ground)`` for a net given all its pin records."""

    is_power = any(r.is_power for r in records)
    is_ground = any(r.is_ground for r in records)
    return is_power, is_ground
