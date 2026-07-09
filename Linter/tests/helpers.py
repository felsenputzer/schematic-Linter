"""Small helpers for building synthetic graphs in unit tests without
needing a real netlist file on disk."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from schematic_linter.graph import CircuitGraph, build_graph
from schematic_linter.parsers.bom_parser import BomEntry
from schematic_linter.parsers.netlist_parser import PinRecord


def pin(
    ref_des: str,
    pin_number: str,
    pin_name: str,
    net_name: Optional[str] = None,
    comp_type: str = "OTHER",
    net_type: Optional[str] = None,
    part_number: str = "PN",
) -> PinRecord:
    return PinRecord(
        net_name=net_name,
        net_type=net_type,
        part_number=part_number,
        comp_type=comp_type,
        ref_des=ref_des,
        pin_number=pin_number,
        status="UNFIXED",
        instance_id=f"Z-test.{ref_des}.{pin_number}",
        pin_name=pin_name,
    )


def graph_from_records(records: Iterable[PinRecord], bom: Optional[Dict[str, BomEntry]] = None) -> CircuitGraph:
    return build_graph(list(records), bom)


def bom_entry(ref_des: str, raw_value: str, description: str = "") -> BomEntry:
    return BomEntry(
        ref_des=ref_des,
        part_number="PN",
        description=description,
        package="0603",
        status="Allowed",
        raw_value=raw_value,
    )
