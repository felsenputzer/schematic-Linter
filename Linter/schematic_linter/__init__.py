"""Topology-aware netlist linter.

Reads a flat Zuken Design Gateway netlist (optionally enriched with an eBOM
and a searchable schematic PDF), builds a component/net graph, recognizes
common circuit topology patterns, checks them against a rule set, and emits
a self-contained HTML report.
"""

__version__ = "0.1.0"
