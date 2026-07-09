from schematic_linter.patterns.voltage_divider import recognize

from ..helpers import graph_from_records, pin


def test_voltage_divider_basic():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="TAP"),
            pin("R2", "1", "A", net_name="TAP"),
            pin("R2", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    matches = recognize(graph)
    assert len(matches) == 1
    m = matches[0]
    assert m.details["top_resistor"] == "R1"
    assert m.details["bottom_resistor"] == "R2"
    assert m.details["tap_net"] == "TAP"
    assert m.details["ground_net"] == "GND"


def test_voltage_divider_requires_exactly_two_resistors_on_tap():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="TAP"),
            pin("R2", "1", "A", net_name="TAP"),
            pin("R2", "2", "B", net_name="GND", net_type="GROUND"),
            pin("R3", "1", "A", net_name="TAP"),
            pin("R3", "2", "B", net_name="OTHER"),
        ]
    )
    assert recognize(graph) == []


def test_real_project_dividers_found(project1_matches):
    dividers = {
        (m.details["top_resistor"], m.details["bottom_resistor"]) for m in project1_matches if m.kind == "voltage_divider"
    }
    assert ("R16", "R17") in dividers
