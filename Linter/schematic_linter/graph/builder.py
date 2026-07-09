"""Builds a ``CircuitGraph`` from parsed netlist (+ optional eBOM) data."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from ..parsers.bom_parser import BomEntry
from ..parsers.netlist_parser import PinRecord
from ..parsers.value_parser import ValueKind, ValueParseError, parse_value
from .anchors import anchor_flags_for_net
from .classifier import classify_component
from .model import CircuitGraph, Component, ComponentKind, Net, Pin

# Only these kinds have an eBOM "VALUE" column that represents an
# engineering quantity (ohms/farads/henries/hertz). For everything else
# (diodes, ICs, connectors, ...) the VALUE column typically holds a part
# variant string (e.g. "BAT54SW", "LM2904BQPWRQ1") which is not a
# component *value* in the sense the rules care about, so we don't attempt
# to numerically parse it.
_VALUE_KIND_FOR_COMPONENT_KIND = {
    ComponentKind.RESISTOR: ValueKind.RESISTANCE,
    ComponentKind.CAPACITOR: ValueKind.CAPACITANCE,
    ComponentKind.INDUCTOR: ValueKind.INDUCTANCE,
    ComponentKind.CRYSTAL: ValueKind.FREQUENCY,
}

VALUE_SOURCE_EBOM = "ebom"
VALUE_SOURCE_UNKNOWN = "unknown"
VALUE_SOURCE_NOT_APPLICABLE = "not_applicable"


def build_graph(
    pin_records: List[PinRecord],
    bom_entries: Optional[Dict[str, BomEntry]] = None,
) -> CircuitGraph:
    """Construct a ``CircuitGraph`` from netlist pin records and eBOM data.

    Components with no matching eBOM entry are still added to the graph,
    with ``value=None`` and ``value_source="unknown"`` -- a missing eBOM
    row is expected, not an error (per spec).
    """

    bom_entries = bom_entries or {}
    graph = CircuitGraph()

    records_by_ref: Dict[str, List[PinRecord]] = defaultdict(list)
    records_by_net: Dict[str, List[PinRecord]] = defaultdict(list)
    for rec in pin_records:
        records_by_ref[rec.ref_des].append(rec)
        if rec.net_name:
            records_by_net[rec.net_name].append(rec)

    for ref_des, records in records_by_ref.items():
        comp_types = list(dict.fromkeys(r.comp_type for r in records if r.comp_type))
        part_number = next((r.part_number for r in records if r.part_number), "")
        bom_entry = bom_entries.get(ref_des)
        bom_description = bom_entry.description if bom_entry else None

        kind = classify_component(ref_des, comp_types, bom_description)

        value = None
        value_kind = _VALUE_KIND_FOR_COMPONENT_KIND.get(kind)
        value_source = VALUE_SOURCE_UNKNOWN if value_kind is not None else VALUE_SOURCE_NOT_APPLICABLE
        if value_kind is not None and bom_entry and bom_entry.raw_value:
            try:
                parsed = parse_value(bom_entry.raw_value, value_kind)
            except ValueParseError:
                parsed = None
            if parsed is not None:
                value = parsed
                value_source = VALUE_SOURCE_EBOM

        pins = [Pin(ref_des=ref_des, pin_number=r.pin_number, pin_name=r.pin_name) for r in records if r.is_connected]
        unconnected_pins = [
            Pin(ref_des=ref_des, pin_number=r.pin_number, pin_name=r.pin_name) for r in records if not r.is_connected
        ]

        component = Component(
            ref_des=ref_des,
            kind=kind,
            part_number=part_number,
            comp_types=comp_types,
            pins=pins,
            unconnected_pins=unconnected_pins,
            value=value,
            value_source=value_source,
            bom_description=bom_description,
        )
        graph.add_component(component)

    for net_name, records in records_by_net.items():
        is_power, is_ground = anchor_flags_for_net(net_name, records)
        pins = [Pin(ref_des=r.ref_des, pin_number=r.pin_number, pin_name=r.pin_name) for r in records]
        net = Net(name=net_name, is_power=is_power, is_ground=is_ground, pins=pins)
        graph.add_net(net)

    for net_name, records in records_by_net.items():
        for rec in records:
            graph.connect(rec.ref_des, net_name, Pin(rec.ref_des, rec.pin_number, rec.pin_name))

    return graph
