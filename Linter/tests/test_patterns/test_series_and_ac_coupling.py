from schematic_linter.patterns.ac_coupling_cap import recognize as recognize_ac_coupling
from schematic_linter.patterns.series_termination import recognize as recognize_series

from ..helpers import graph_from_records, pin


def test_series_termination_basic():
    graph = graph_from_records(
        [
            pin("U1", "1", "OUT", net_name="A", comp_type="IC"),
            pin("R1", "1", "X", net_name="A"),
            pin("R1", "2", "Y", net_name="B"),
            pin("U2", "1", "IN+", net_name="B", comp_type="IC"),
        ]
    )
    matches = recognize_series(graph)
    assert len(matches) == 1
    assert matches[0].details["resistor"] == "R1"
    assert "U2" in matches[0].details["ic_refs"]


def test_series_termination_not_matched_for_pull_up_shape():
    # power/ground on either side is a pull-up/down, not series termination
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="SIG"),
            pin("U1", "1", "IN", net_name="SIG", comp_type="IC"),
        ]
    )
    assert recognize_series(graph) == []


def test_ac_coupling_cap_between_two_signal_nets():
    graph = graph_from_records(
        [
            pin("C1", "1", "A", net_name="SIG1"),
            pin("C1", "2", "B", net_name="SIG2"),
        ]
    )
    matches = recognize_ac_coupling(graph)
    assert len(matches) == 1
    assert matches[0].details == {"capacitor": "C1", "net_a": "SIG1", "net_b": "SIG2"}


def test_ac_coupling_not_matched_when_one_side_is_ground():
    graph = graph_from_records(
        [
            pin("C1", "1", "A", net_name="SIG1"),
            pin("C1", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    assert recognize_ac_coupling(graph) == []
