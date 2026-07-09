"""Serialize/deserialize a ``CircuitGraph`` to/from a standalone JSON file.

The graph is saved as its own artifact (independent of report generation)
so it can be reused later -- e.g. by a future rule, a different report
format, or ad-hoc inspection -- without re-parsing the original netlist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..parsers.value_parser import ParsedValue
from .model import CircuitGraph, Component, ComponentKind, Net, Pin

_SCHEMA_VERSION = 1


def _value_to_dict(value: Optional[ParsedValue]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    return {
        "raw": value.raw,
        "magnitude": value.magnitude,
        "unit": value.unit,
        "display": value.display,
    }


def _value_from_dict(data: Optional[Dict[str, Any]]) -> Optional[ParsedValue]:
    if data is None:
        return None
    return ParsedValue(raw=data["raw"], magnitude=data["magnitude"], unit=data["unit"], display=data["display"])


def graph_to_dict(graph: CircuitGraph, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    components = {
        ref_des: {
            "ref_des": c.ref_des,
            "kind": c.kind.value,
            "part_number": c.part_number,
            "comp_types": c.comp_types,
            "pins": [{"pin_number": p.pin_number, "pin_name": p.pin_name} for p in c.pins],
            "value": _value_to_dict(c.value),
            "value_source": c.value_source,
            "bom_description": c.bom_description,
        }
        for ref_des, c in graph.components.items()
    }
    nets = {
        name: {
            "name": n.name,
            "is_power": n.is_power,
            "is_ground": n.is_ground,
            "pins": [{"ref_des": p.ref_des, "pin_number": p.pin_number, "pin_name": p.pin_name} for p in n.pins],
        }
        for name, n in graph.nets.items()
    }
    return {
        "schema_version": _SCHEMA_VERSION,
        "metadata": metadata or {},
        "components": components,
        "nets": nets,
    }


def dict_to_graph(data: Dict[str, Any]) -> CircuitGraph:
    graph = CircuitGraph()

    for ref_des, c in data["components"].items():
        component = Component(
            ref_des=c["ref_des"],
            kind=ComponentKind(c["kind"]),
            part_number=c["part_number"],
            comp_types=c.get("comp_types", []),
            pins=[Pin(ref_des=ref_des, pin_number=p["pin_number"], pin_name=p["pin_name"]) for p in c["pins"]],
            value=_value_from_dict(c.get("value")),
            value_source=c.get("value_source", "unknown"),
            bom_description=c.get("bom_description"),
        )
        graph.add_component(component)

    for name, n in data["nets"].items():
        net = Net(
            name=n["name"],
            is_power=n["is_power"],
            is_ground=n["is_ground"],
            pins=[Pin(ref_des=p["ref_des"], pin_number=p["pin_number"], pin_name=p["pin_name"]) for p in n["pins"]],
        )
        graph.add_net(net)

    for name, n in data["nets"].items():
        for p in n["pins"]:
            graph.connect(p["ref_des"], name, Pin(p["ref_des"], p["pin_number"], p["pin_name"]))

    return graph


def save_graph(graph: CircuitGraph, path: Path, metadata: Optional[Dict[str, Any]] = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(graph_to_dict(graph, metadata), f, indent=2, sort_keys=True)


def load_graph(path: Path) -> CircuitGraph:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return dict_to_graph(data)
