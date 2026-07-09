"""Core data model: components, nets, pins, and the circuit graph.

The graph is a bipartite ``networkx.MultiGraph`` with two kinds of nodes --
``("component", ref_des)`` and ``("net", net_name)`` -- connected by edges
that carry the pin metadata (pin number/name) of that particular
connection. Keeping components and nets as distinct node types (rather than
collapsing to a plain component-to-component graph) preserves exactly the
information the pattern recognizers need: which *net* ties things together,
and how many other things are on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional

import networkx as nx

from ..parsers.value_parser import ParsedValue


class ComponentKind(str, Enum):
    RESISTOR = "RESISTOR"
    CAPACITOR = "CAPACITOR"
    INDUCTOR = "INDUCTOR"
    DIODE = "DIODE"
    TRANSISTOR = "TRANSISTOR"
    IC = "IC"
    CRYSTAL = "CRYSTAL"
    CONNECTOR = "CONNECTOR"
    TESTPOINT = "TESTPOINT"
    OTHER = "OTHER"


NODE_KIND_COMPONENT = "component"
NODE_KIND_NET = "net"


@dataclass(frozen=True)
class Pin:
    ref_des: str
    pin_number: str
    pin_name: str


@dataclass
class Component:
    ref_des: str
    kind: ComponentKind
    part_number: str
    comp_types: List[str] = field(default_factory=list)
    pins: List[Pin] = field(default_factory=list)
    unconnected_pins: List[Pin] = field(default_factory=list)
    value: Optional[ParsedValue] = None
    value_source: str = "unknown"  # "ebom" | "unknown" | "not_applicable"
    bom_description: Optional[str] = None

    def pin_names(self) -> List[str]:
        return [p.pin_name for p in self.pins]

    @property
    def has_known_value(self) -> bool:
        return self.value_source == "ebom" and self.value is not None


@dataclass
class Net:
    name: str
    is_power: bool = False
    is_ground: bool = False
    pins: List[Pin] = field(default_factory=list)

    @property
    def pin_count(self) -> int:
        return len(self.pins)

    def ref_des_set(self) -> set:
        return {p.ref_des for p in self.pins}

    @property
    def is_anchor(self) -> bool:
        return self.is_power or self.is_ground


class CircuitGraph:
    """Bipartite component/net graph plus convenience lookups."""

    def __init__(self) -> None:
        self.graph = nx.MultiGraph()
        self.components: Dict[str, Component] = {}
        self.nets: Dict[str, Net] = {}

    # -- construction -----------------------------------------------------

    def add_component(self, component: Component) -> None:
        self.components[component.ref_des] = component
        self.graph.add_node((NODE_KIND_COMPONENT, component.ref_des), kind=NODE_KIND_COMPONENT)

    def add_net(self, net: Net) -> None:
        self.nets[net.name] = net
        self.graph.add_node(
            (NODE_KIND_NET, net.name),
            kind=NODE_KIND_NET,
            is_power=net.is_power,
            is_ground=net.is_ground,
        )

    def connect(self, ref_des: str, net_name: str, pin: Pin) -> None:
        self.graph.add_edge(
            (NODE_KIND_COMPONENT, ref_des),
            (NODE_KIND_NET, net_name),
            pin_number=pin.pin_number,
            pin_name=pin.pin_name,
        )

    # -- lookups ------------------------------------------------------------

    def get_component(self, ref_des: str) -> Optional[Component]:
        return self.components.get(ref_des)

    def get_net(self, name: str) -> Optional[Net]:
        return self.nets.get(name)

    def nets_of(self, ref_des: str) -> List[str]:
        node = (NODE_KIND_COMPONENT, ref_des)
        if node not in self.graph:
            return []
        return [n[1] for n in self.graph.neighbors(node)]

    def components_on_net(self, net_name: str) -> List[str]:
        node = (NODE_KIND_NET, net_name)
        if node not in self.graph:
            return []
        return [n[1] for n in self.graph.neighbors(node)]

    def pins_on_edge(self, ref_des: str, net_name: str) -> List[Pin]:
        """All pins of ``ref_des`` that connect it to ``net_name`` (usually one)."""

        data = self.graph.get_edge_data((NODE_KIND_COMPONENT, ref_des), (NODE_KIND_NET, net_name))
        if not data:
            return []
        return [Pin(ref_des=ref_des, pin_number=d["pin_number"], pin_name=d["pin_name"]) for d in data.values()]

    def components_by_kind(self, kind: ComponentKind) -> List[Component]:
        return [c for c in self.components.values() if c.kind == kind]

    def other_pins_of_component(self, ref_des: str, exclude_net: str) -> List[str]:
        """Net names ``ref_des`` connects to, other than ``exclude_net``."""

        return [n for n in self.nets_of(ref_des) if n != exclude_net]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CircuitGraph(components={len(self.components)}, nets={len(self.nets)})"
